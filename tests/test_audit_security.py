from __future__ import annotations

import os

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fusion_health.config import HealthConfig
from fusion_health.api.app import create_app


@pytest.fixture(autouse=True)
def _clear_sessions(monkeypatch):
    from fusion_health.api.routes.chat import _sessions, _session_times
    _sessions.clear()
    _session_times.clear()
    saved = os.environ.get("FUSION_HEALTH_API_KEY")
    yield
    _sessions.clear()
    _session_times.clear()
    if saved is None:
        os.environ.pop("FUSION_HEALTH_API_KEY", None)
    else:
        os.environ["FUSION_HEALTH_API_KEY"] = saved


class TestMiddlewarePathBypass:
    def test_protected_api_path_requires_auth(self):
        os.environ["FUSION_HEALTH_API_KEY"] = "secret-key"
        cfg = HealthConfig()
        app = create_app(cfg)
        from starlette.testclient import TestClient
        unauth = TestClient(app)
        resp = unauth.post("/api/v1/ehr/summary", json={"clinical_notes": "x"})
        assert resp.status_code == 401

    def test_normalized_double_slash_path_requires_auth(self):
        from fusion_health.api.middleware import _normalize_path
        assert _normalize_path("//api//v1//ehr//summary") == "/api/v1/ehr/summary"
        assert _normalize_path("/api/v1/health") == "/api/v1/health"

    def test_non_api_path_not_protected(self):
        os.environ["FUSION_HEALTH_API_KEY"] = "secret-key"
        cfg = HealthConfig()
        app = create_app(cfg)
        from starlette.testclient import TestClient
        c = TestClient(app, headers={"X-API-Key": "secret-key"})
        resp = c.get("/docs")
        assert resp.status_code == 200


class TestSessionOwnerIsolation:
    def test_sessions_keyed_by_owner_and_list_scoped(self):
        from fusion_health.api.routes.chat import _sessions, _session_times
        from fusion_health.conversation import ConversationSession

        cfg = HealthConfig()
        sess_a = ConversationSession(cfg)
        sess_a.start("sess-a")
        _sessions[("owner-a", "sess-a")] = sess_a
        _session_times[("owner-a", "sess-a")] = 0.0

        sess_b = ConversationSession(cfg)
        sess_b.start("sess-b")
        _sessions[("owner-b", "sess-b")] = sess_b
        _session_times[("owner-b", "sess-b")] = 0.0

        import asyncio
        from fusion_health.api.routes.chat import list_sessions, send_message
        from starlette.requests import Request

        class FakeScope:
            def __init__(self, owner):
                self._state = {"owner_id": owner}

        def fake_request(owner):
            req = MagicMock(spec=Request)
            req.app.state.config = cfg
            req.state = MagicMock()
            req.state.owner_id = owner
            return req

        a_list = asyncio.run(list_sessions(fake_request("owner-a")))
        a_ids = {s["session_id"] for s in a_list["sessions"]}
        assert a_ids == {"sess-a"}

        msg = asyncio.run(send_message(fake_request("owner-b"), MagicMock(
            session_id="sess-a", message="hi",
        )))
        assert msg.status_code == 404

    def test_cross_key_isolation_via_env(self):
        os.environ["FUSION_HEALTH_API_KEY"] = "key-a"
        cfg = HealthConfig()
        cfg.pubmed_enabled = False
        cfg.semantic_scholar_enabled = False
        app = create_app(cfg)
        from starlette.testclient import TestClient
        owner_a = TestClient(app, headers={"X-API-Key": "key-a"})
        owner_a.post("/api/v1/chat/start", json={"session_id": "sid-a"})

        other_key = TestClient(app, headers={"X-API-Key": "wrong-key"})
        msg = other_key.post("/api/v1/chat/message", json={
            "session_id": "sid-a", "message": "hi",
        })
        assert msg.status_code == 401


class TestStreamHistoryConsistency:
    def test_stream_adds_assistant_message_to_history(self):
        os.environ["FUSION_HEALTH_API_KEY"] = "key-stream"
        cfg = HealthConfig()
        cfg.pubmed_enabled = False
        cfg.semantic_scholar_enabled = False
        app = create_app(cfg)
        from starlette.testclient import TestClient
        client = TestClient(app, headers={"X-API-Key": "key-stream"})
        client.post("/api/v1/chat/start", json={"session_id": "stream-sess"})

        async def fake_stream(*args, **kwargs):
            yield "Hello"
            yield " patient"

        with patch("fusion_health.api.routes.chat.get_gateway") as MockGW:
            mock_gw = MagicMock()
            mock_gw.chat_stream = fake_stream
            mock_gw.close = AsyncMock()
            MockGW.return_value = mock_gw
            resp = client.post("/api/v1/chat/message/stream", json={
                "session_id": "stream-sess", "message": "hi",
            })
            assert resp.status_code == 200

        from fusion_health.api.routes.chat import _sessions
        key = next(k for k in _sessions if k[1] == "stream-sess")
        session = _sessions[key]
        messages = session.memory.get_messages()
        assistant_msgs = [m for m in messages if m["role"] == "assistant"]
        assert any("Hello" in m["content"] for m in assistant_msgs)


class TestAuditKeyProfile:
    def test_prod_missing_secret_raises(self, monkeypatch):
        from fusion_health import audit
        monkeypatch.delenv("FUSION_HEALTH_AUDIT_HMAC_KEY", raising=False)
        monkeypatch.delenv("FUSION_HEALTH_API_KEY", raising=False)
        monkeypatch.setenv("FUSION_PROFILE", "prod")
        with pytest.raises(RuntimeError, match="FUSION_HEALTH_AUDIT_HMAC_KEY"):
            audit._audit_key()

    def test_prod_missing_secret_fails_fast_in_log_access(self, monkeypatch, tmp_path):
        from fusion_health import audit
        monkeypatch.delenv("FUSION_HEALTH_AUDIT_HMAC_KEY", raising=False)
        monkeypatch.delenv("FUSION_HEALTH_API_KEY", raising=False)
        monkeypatch.setenv("FUSION_PROFILE", "prod")
        monkeypatch.setenv("FUSION_HEALTH_AUDIT_LOG", str(tmp_path / "audit.log"))
        with pytest.raises(RuntimeError, match="FUSION_HEALTH_AUDIT_HMAC_KEY"):
            audit.log_access("owner-1", "GET", "/api/v1/ehr/summary", "ehr_summary", "ok", "phi")

    def test_dev_empty_key_warns_and_still_logs(self, monkeypatch, tmp_path, caplog):
        import logging as _logging
        from fusion_health import audit
        audit._empty_key_warned = False
        monkeypatch.delenv("FUSION_HEALTH_AUDIT_HMAC_KEY", raising=False)
        monkeypatch.delenv("FUSION_HEALTH_API_KEY", raising=False)
        monkeypatch.delenv("FUSION_PROFILE", raising=False)
        log_path = tmp_path / "audit.log"
        monkeypatch.setenv("FUSION_HEALTH_AUDIT_LOG", str(log_path))
        with caplog.at_level(_logging.WARNING, logger="fusion_health.audit"):
            audit.log_access("owner-2", "GET", "/api/v1/tcm/analyze", "tcm_analyze", "ok", "phi")
        assert any("FUSION_HEALTH_AUDIT_HMAC_KEY" in r.message for r in caplog.records)
        assert log_path.exists()
        verified, tampered = audit.verify_log_file(log_path)
        assert verified == 1 and tampered == 0
        assert "fusion-health-audit-default" not in log_path.read_text()

    def test_explicit_key_no_warning(self, monkeypatch, tmp_path, caplog):
        import logging as _logging
        from fusion_health import audit
        monkeypatch.setenv("FUSION_HEALTH_AUDIT_HMAC_KEY", "explicit-key")
        log_path = tmp_path / "audit.log"
        monkeypatch.setenv("FUSION_HEALTH_AUDIT_LOG", str(log_path))
        with caplog.at_level(_logging.WARNING, logger="fusion_health.audit"):
            audit.log_access("owner-3", "GET", "/x", "act", "ok")
        assert not any("FUSION_HEALTH_AUDIT_HMAC_KEY" in r.message for r in caplog.records)


class TestProcessTitle:
    def test_set_process_title(self):
        from fusion_health.api.app import _set_process_title
        cfg = HealthConfig()
        _set_process_title(cfg)
        try:
            import setproctitle
            assert setproctitle.getproctitle() == f"fusion-health serve :{cfg.api_port}"
        except ImportError:
            pass

    def test_set_process_title_fallback_safe(self, monkeypatch):
        import builtins
        from fusion_health.api import app as app_module
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "setproctitle":
                raise ImportError("no setproctitle")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        app_module._set_process_title(HealthConfig())


class TestAuditSeqContinuity:
    def test_seq_continues_across_simulated_restart(self, monkeypatch, tmp_path):
        import json as _json
        from fusion_health import audit
        monkeypatch.setenv("FUSION_HEALTH_AUDIT_HMAC_KEY", "k")
        log_path = tmp_path / "audit.log"
        monkeypatch.setenv("FUSION_HEALTH_AUDIT_LOG", str(log_path))
        # fresh counters, as in a brand-new process
        audit._seq = 0
        audit._seq_inited = False
        audit.log_access("o", "GET", "/a", "act", "ok")
        audit.log_access("o", "GET", "/b", "act", "ok")
        # simulate process restart: fresh counters, same log file
        audit._seq = 0
        audit._seq_inited = False
        audit.log_access("o", "GET", "/c", "act", "ok")
        lines = [ln for ln in log_path.read_text().splitlines() if ln.strip()]
        seqs = [_json.loads(ln.rsplit("\t", 1)[0])["seq"] for ln in lines]
        assert seqs == [1, 2, 3]
        verified, tampered = audit.verify_log_file(log_path)
        assert verified == 3 and tampered == 0

    def test_seq_gap_detection_still_works(self, monkeypatch, tmp_path):
        import json as _json
        from fusion_health import audit
        monkeypatch.setenv("FUSION_HEALTH_AUDIT_HMAC_KEY", "k")
        log_path = tmp_path / "audit.log"
        monkeypatch.setenv("FUSION_HEALTH_AUDIT_LOG", str(log_path))
        audit.log_access("o", "GET", "/a", "act", "ok")
        # tamper: rewrite the line with a bogus seq
        line = log_path.read_text().splitlines()[0]
        body, sig = line.rsplit("\t", 1)
        event = _json.loads(body)
        event["seq"] = 99
        tampered_line = _json.dumps(event, ensure_ascii=False, sort_keys=True) + "\t" + sig
        log_path.write_text(tampered_line + "\n")
        verified, tampered = audit.verify_log_file(log_path)
        assert tampered >= 1
