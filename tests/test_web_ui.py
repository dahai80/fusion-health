from __future__ import annotations

import os

import pytest
from starlette.testclient import TestClient

from fusion_health.config import HealthConfig


@pytest.fixture()
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("FUSION_HEALTH_API_KEY", "test-key-web-ui")
    cfg = HealthConfig()
    cfg.pubmed_enabled = False
    cfg.semantic_scholar_enabled = False
    cfg.audit_log_path = tmp_path / "audit.log"
    cfg.mlx_url = "http://127.0.0.1:1/v1"
    from fusion_health.api.app import create_app
    app = create_app(cfg)
    c = TestClient(app)
    c.headers.update({"X-API-Key": "test-key-web-ui"})
    return c


class TestWebUI:
    def test_ui_index_served(self, client):
        r = client.get("/ui")
        assert r.status_code == 200
        assert "Fusion-Health Console" in r.text

    def test_ui_assets_served(self, client):
        r = client.get("/ui/assets/app.js")
        assert r.status_code == 200
        assert "X-API-Key" in r.text

    def test_ui_index_not_in_openapi(self, client):
        r = client.get("/openapi.json")
        assert "/ui" not in r.json()["paths"]


class TestAuditRoutes:
    def test_verify_empty_log(self, client):
        r = client.get("/api/v1/audit/verify")
        assert r.status_code == 200
        body = r.json()
        assert body["intact"] is True
        assert body["verified"] == 0
        assert body["tampered"] == 0

    def test_verify_and_recent_signed_log(self, client, monkeypatch, tmp_path):
        monkeypatch.setenv("FUSION_HEALTH_AUDIT_HMAC_KEY", "test-key-web-ui")
        import fusion_health.audit as audit_mod
        audit_mod._empty_key_warned = False
        audit_mod._seq = 0
        audit_mod._seq_inited = False
        monkeypatch.setenv("FUSION_HEALTH_AUDIT_LOG", str(tmp_path / "audit.log"))
        audit_mod.log_access("owner-1", "POST", "/api/v1/ehr/summary", "summary", "ok", "notes", "req-1")
        r = client.get("/api/v1/audit/verify")
        body = r.json()
        assert body["tampered"] == 0
        assert body["verified"] >= 1
        r2 = client.get("/api/v1/audit/recent?limit=10")
        events = r2.json()["events"]
        assert len(events) >= 1
        assert events[-1]["owner_id"] == "owner-1"
        assert "phi_input" not in json_keys(events[-1])
        os.environ.pop("FUSION_HEALTH_AUDIT_LOG", None)


def json_keys(d: dict) -> set:
    return set(d.keys())
