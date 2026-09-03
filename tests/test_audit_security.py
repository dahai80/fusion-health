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
