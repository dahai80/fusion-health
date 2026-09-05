from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fusion_health.config import HealthConfig, _parse_bool
from fusion_health.llm_gateway import LLMGateway
from fusion_health.logging_config import configure_logging


# ---------- config ----------

class TestConfig:
    def test_parse_bool_variants(self):
        assert _parse_bool("true") is True
        assert _parse_bool("YES") is True
        assert _parse_bool("1") is True
        assert _parse_bool("on") is True
        assert _parse_bool("false") is False
        assert _parse_bool("off") is False
        assert _parse_bool("") is False
        assert _parse_bool(True) is True
        assert _parse_bool(0) is False
        assert _parse_bool(2.5) is True
        assert _parse_bool("garbage") is False

    def test_from_env_bad_cast_keeps_default(self, monkeypatch):
        monkeypatch.setenv("FUSION_HEALTH_MAX_TOKENS", "not-a-number")
        monkeypatch.setenv("FUSION_HEALTH_TIMEOUT", "xx")
        cfg = HealthConfig.from_env()
        assert cfg.max_tokens == 2048
        assert cfg.timeout == 60.0

    def test_from_env_valid_cast(self, monkeypatch):
        monkeypatch.setenv("FUSION_HEALTH_MAX_TOKENS", "512")
        monkeypatch.setenv("FUSION_HEALTH_TEMPERATURE", "0.7")
        monkeypatch.setenv("FUSION_HEALTH_API_PORT", "9999")
        monkeypatch.setenv("FUSION_HEALTH_RATE_LIMIT_RPM", "30")
        monkeypatch.setenv("FUSION_HEALTH_SESSION_TTL", "900")
        cfg = HealthConfig.from_env()
        assert cfg.max_tokens == 512
        assert cfg.temperature == 0.7
        assert cfg.api_port == 9999
        assert cfg.rate_limit_rpm == 30
        assert cfg.session_ttl_seconds == 900

    def test_offline_disables_external_sources(self, monkeypatch):
        monkeypatch.setenv("FUSION_HEALTH_OFFLINE", "1")
        cfg = HealthConfig.from_env()
        assert cfg.offline is True
        assert cfg.pubmed_enabled is False
        assert cfg.semantic_scholar_enabled is False

    def test_env_disable_individual_sources(self, monkeypatch):
        monkeypatch.setenv("FUSION_HEALTH_PUBMED_ENABLED", "0")
        monkeypatch.setenv("FUSION_HEALTH_S2_ENABLED", "0")
        cfg = HealthConfig.from_env()
        assert cfg.pubmed_enabled is False
        assert cfg.semantic_scholar_enabled is False

    def test_yaml_overrides_applied(self, monkeypatch, tmp_path):
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        cfgdir = fake_home / ".fusion-health"
        cfgdir.mkdir()
        (cfgdir / "config.yaml").write_text(
            "model: yaml-model\ntemperature: 0.9\nmax_tokens: 100\npubmed_enabled: true\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(Path, "home", lambda: fake_home)
        cfg = HealthConfig.from_env()
        assert cfg.model == "yaml-model"
        assert cfg.temperature == 0.9
        assert cfg.max_tokens == 100

    def test_yaml_bad_cast_keeps_default(self, monkeypatch, tmp_path):
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        cfgdir = fake_home / ".fusion-health"
        cfgdir.mkdir()
        (cfgdir / "config.yaml").write_text(
            "max_tokens: not-int\ntemperature: not-float\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(Path, "home", lambda: fake_home)
        cfg = HealthConfig.from_env()
        assert cfg.max_tokens == 2048
        assert cfg.temperature == 0.1

    def test_mlx_api_key_from_settings_json(self, monkeypatch, tmp_path):
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        mlxdir = fake_home / ".fusion-mlx"
        mlxdir.mkdir()
        (mlxdir / "settings.json").write_text(
            json.dumps({"auth": {"api_key": "key-from-settings"}}),
            encoding="utf-8",
        )
        monkeypatch.setattr(Path, "home", lambda: fake_home)
        monkeypatch.delenv("FUSION_MLX_API_KEY", raising=False)
        monkeypatch.delenv("FUSION_HEALTH_MLX_API_KEY", raising=False)
        cfg = HealthConfig.from_env()
        assert cfg.mlx_api_key == "key-from-settings"


# ---------- logging ----------

class TestLogging:
    def test_configure_logging_writes_file(self, monkeypatch, tmp_path):
        monkeypatch.setenv("FUSION_HEALTH_LOG_DIR", str(tmp_path))
        monkeypatch.setenv("FUSION_HEALTH_LOG_LEVEL", "DEBUG")
        configure_logging()
        log = logging.getLogger("fusion_health.test")
        log.info("hardening-log-line")
        assert (tmp_path / "app.log").exists()
        assert "hardening-log-line" in (tmp_path / "app.log").read_text()


# ---------- llm gateway ----------

class TestLLMGateway:
    @pytest.mark.asyncio
    async def test_auth_headers_with_route_and_key(self):
        cfg = HealthConfig()
        cfg.mlx_route = "chat"
        cfg.mlx_api_key = "secret"
        gw = LLMGateway(cfg)
        h = gw._auth_headers()
        assert h["X-Fusion-Route"] == "chat"
        assert h["Authorization"] == "Bearer secret"

    @pytest.mark.asyncio
    async def test_auth_headers_empty_when_unset(self):
        cfg = HealthConfig()
        cfg.mlx_route = ""
        cfg.mlx_api_key = ""
        gw = LLMGateway(cfg)
        assert gw._auth_headers() == {}

    @pytest.mark.asyncio
    async def test_chat_empty_content_guard(self):
        cfg = HealthConfig()
        gw = LLMGateway(cfg)
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"choices": [{"message": {"content": "   "}}]}
        mock_resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        gw._get_client = AsyncMock(return_value=mock_client)
        with patch("fusion_health.llm_gateway.with_retry", new=_no_retry):
            result = await gw.chat(messages=[{"role": "user", "content": "hi"}])
        assert result.error == "empty_content"
        assert result.content == ""

    @pytest.mark.asyncio
    async def test_chat_http_status_error(self):
        cfg = HealthConfig()
        gw = LLMGateway(cfg)
        import httpx
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "err", request=MagicMock(), response=MagicMock(status_code=500),
        )
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        gw._get_client = AsyncMock(return_value=mock_client)
        with patch("fusion_health.llm_gateway.with_retry", new=_no_retry):
            result = await gw.chat(messages=[{"role": "user", "content": "hi"}])
        assert result.error == "HTTP 500"

    @pytest.mark.asyncio
    async def test_chat_missing_key(self):
        cfg = HealthConfig()
        gw = LLMGateway(cfg)
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"choices": [{}]}
        mock_resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        gw._get_client = AsyncMock(return_value=mock_client)
        with patch("fusion_health.llm_gateway.with_retry", new=_no_retry):
            result = await gw.chat(messages=[{"role": "user", "content": "hi"}])
        assert result.error.startswith("response_missing_key")

    @pytest.mark.asyncio
    async def test_parse_structured_strips_fenced_json(self):
        cfg = HealthConfig()
        gw = LLMGateway(cfg)
        payload = json.dumps({
            "chief_complaint": "fever",
            "history": "",
            "examination_findings": "",
            "diagnosis": "",
            "treatment_plan": "",
            "confidence_notes": "",
        })
        fenced = "```json\n" + payload + "\n```"
        from fusion_health.schemas.ehr import ClinicalSummary
        result = gw._parse_structured(fenced, ClinicalSummary, "m")
        assert result.parsed is not None
        assert not result.error

    @pytest.mark.asyncio
    async def test_parse_structured_bad_json(self):
        cfg = HealthConfig()
        gw = LLMGateway(cfg)
        result = gw._parse_structured("not json at all", dict, "m")
        assert "json_decode_error" in result.error

    @pytest.mark.asyncio
    async def test_close_releases_ref(self):
        cfg = HealthConfig()
        gw = LLMGateway(cfg)
        gw._client = MagicMock()
        await gw.close()
        assert gw._client is None

    @pytest.mark.asyncio
    async def test_resolve_model_exact_match(self):
        cfg = HealthConfig()
        gw = LLMGateway(cfg)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": [{"id": "mlx-community--Qwen3.5-9B-4bit"}, {"id": "Qwen3.8-27B-4bit"}]}
        mock_resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        gw._get_client = AsyncMock(return_value=mock_client)
        resolved = await gw._resolve_model("Qwen3.8-27B-4bit")
        assert resolved == "Qwen3.8-27B-4bit"

    @pytest.mark.asyncio
    async def test_resolve_model_shorthand_alias(self):
        cfg = HealthConfig()
        gw = LLMGateway(cfg)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": [{"id": "mlx-community--Qwen3.5-9B-4bit"}]}
        mock_resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        gw._get_client = AsyncMock(return_value=mock_client)
        resolved = await gw._resolve_model("Qwen3.5-9B-4bit")
        assert resolved == "mlx-community--Qwen3.5-9B-4bit"

    @pytest.mark.asyncio
    async def test_resolve_model_not_found_keeps_requested(self):
        cfg = HealthConfig()
        gw = LLMGateway(cfg)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": [{"id": "other-model"}]}
        mock_resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        gw._get_client = AsyncMock(return_value=mock_client)
        resolved = await gw._resolve_model("Qwen3.5-9B-4bit")
        assert resolved == "Qwen3.5-9B-4bit"

    @pytest.mark.asyncio
    async def test_resolve_model_cached(self):
        cfg = HealthConfig()
        gw = LLMGateway(cfg)
        gw._resolved_model = "cached-model"
        mock_client = MagicMock()
        mock_client.get = AsyncMock()
        gw._get_client = AsyncMock(return_value=mock_client)
        resolved = await gw._resolve_model("anything")
        assert resolved == "cached-model"
        mock_client.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_resolve_model_non_200_keeps_requested(self):
        cfg = HealthConfig()
        gw = LLMGateway(cfg)
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        gw._get_client = AsyncMock(return_value=mock_client)
        resolved = await gw._resolve_model("Qwen3.5-9B-4bit")
        assert resolved == "Qwen3.5-9B-4bit"

    @pytest.mark.asyncio
    async def test_chat_401_error_includes_hint(self):
        cfg = HealthConfig()
        gw = LLMGateway(cfg)
        import httpx
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "err", request=MagicMock(), response=MagicMock(status_code=401),
        )
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_models = MagicMock()
        mock_models.status_code = 200
        mock_models.json.return_value = {"data": [{"id": cfg.model}]}
        mock_models.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_models)
        gw._get_client = AsyncMock(return_value=mock_client)
        with patch("fusion_health.llm_gateway.with_retry", new=_no_retry):
            result = await gw.chat(messages=[{"role": "user", "content": "hi"}])
        assert result.error.startswith("HTTP 401")
        assert "401: auth failed" in result.error

    @pytest.mark.asyncio
    async def test_chat_404_error_includes_hint(self):
        cfg = HealthConfig()
        gw = LLMGateway(cfg)
        import httpx
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "err", request=MagicMock(), response=MagicMock(status_code=404),
        )
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_models = MagicMock()
        mock_models.status_code = 200
        mock_models.json.return_value = {"data": [{"id": cfg.model}]}
        mock_models.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_models)
        gw._get_client = AsyncMock(return_value=mock_client)
        with patch("fusion_health.llm_gateway.with_retry", new=_no_retry):
            result = await gw.chat(messages=[{"role": "user", "content": "hi"}])
        assert result.error.startswith("HTTP 404")
        assert "model not loaded" in result.error

    @pytest.mark.asyncio
    async def test_chat_stream_yields_tokens(self):
        cfg = HealthConfig()
        gw = LLMGateway(cfg)
        lines = [
            "data: " + json.dumps({"choices": [{"delta": {"content": "Hel"}}]}),
            "data: " + json.dumps({"choices": [{"delta": {"content": "lo"}}]}),
            "data: [DONE]",
        ]

        class FakeStream:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                return False
            async def aiter_lines(self):
                for ln in lines:
                    yield ln
            def raise_for_status(self):
                pass

        mock_client = MagicMock()
        mock_client.stream = MagicMock(return_value=FakeStream())
        gw._get_client = AsyncMock(return_value=mock_client)
        tokens = []
        async for t in gw.chat_stream(messages=[{"role": "user", "content": "hi"}]):
            tokens.append(t)
        assert "".join(tokens) == "Hello"


async def _no_retry(coro_factory):
    return await coro_factory()


# ---------- gateway provider ----------

class TestGatewayProvider:
    def test_get_gateway_singleton(self):
        import fusion_health.api.gateway_provider as gp
        gp._shared_gateway = None
        g1 = gp.get_gateway(HealthConfig())
        g2 = gp.get_gateway()
        assert g1 is g2
        gp._shared_gateway = None

    @pytest.mark.asyncio
    async def test_close_gateway(self):
        import fusion_health.api.gateway_provider as gp
        gp._shared_gateway = None
        gp.get_gateway(HealthConfig())
        assert gp._shared_gateway is not None
        await gp.close_gateway()
        assert gp._shared_gateway is None


# ---------- metrics + middleware ----------

class TestMetricsAndMiddleware:
    def test_metrics_route_available(self):
        from fusion_health.api.app import create_app
        cfg = HealthConfig()
        cfg.pubmed_enabled = False
        cfg.semantic_scholar_enabled = False
        app = create_app(cfg)
        from starlette.testclient import TestClient
        c = TestClient(app)
        resp = c.get("/api/v1/metrics")
        assert resp.status_code == 200
        body = resp.json()
        assert body["available"] is True
        assert "total_requests" in body
        assert "rate_limit_backend" in body

    def test_metrics_snapshot_shape(self):
        from fusion_health.api.middleware import APIKeyMiddleware
        mw = APIKeyMiddleware(MagicMock())
        snap = mw.metrics_snapshot()
        assert snap["rate_limit_backend"] in ("sqlite", "memory")
        assert "tracked_owners" in snap

    def test_rate_limiter_disabled_when_zero(self):
        from fusion_health.api.middleware import RateLimiter
        rl = RateLimiter(0)
        assert rl.allow("any") is True

    def test_rate_limiter_local_enforces(self):
        from fusion_health.api.middleware import RateLimiter
        rl = RateLimiter(2)
        assert rl.allow("o1") is True
        assert rl.allow("o1") is True
        assert rl.allow("o1") is False
        assert rl.allow("o2") is True

    def test_rate_limiter_sqlite_shared(self, tmp_path):
        from fusion_health.api.middleware import RateLimiter
        db = tmp_path / "rl.db"
        os.environ["FUSION_HEALTH_RATE_LIMIT_DB"] = str(db)
        try:
            rl = RateLimiter(1)
            assert rl._db_path == str(db)
            assert rl.allow("owner-x") is True
            assert rl.allow("owner-x") is False
        finally:
            os.environ.pop("FUSION_HEALTH_RATE_LIMIT_DB", None)


# ---------- health ----------

class TestHealthRoutes:
    def test_health_degraded_when_backend_down(self):
        from fusion_health.api.app import create_app
        cfg = HealthConfig()
        cfg.pubmed_enabled = False
        cfg.semantic_scholar_enabled = False
        cfg.mlx_url = "http://127.0.0.1:1/v1"
        app = create_app(cfg)
        from starlette.testclient import TestClient
        c = TestClient(app)
        resp = c.get("/api/v1/health")
        assert resp.status_code == 503
        body = resp.json()
        assert body["status"] == "degraded"
        assert "data_files" in body

    def test_health_ready_degraded(self):
        from fusion_health.api.app import create_app
        cfg = HealthConfig()
        cfg.pubmed_enabled = False
        cfg.semantic_scholar_enabled = False
        cfg.mlx_url = "http://127.0.0.1:1/v1"
        app = create_app(cfg)
        from starlette.testclient import TestClient
        c = TestClient(app)
        resp = c.get("/api/v1/health/ready")
        assert resp.status_code == 503
        assert resp.json()["status"] == "degraded"

    def test_data_file_status_loaded(self):
        from fusion_health.api.routes.health import _data_file_status
        cfg = HealthConfig()
        status = _data_file_status(cfg)
        assert status["icd10_cn"] == "loaded"
        assert status["drg"] == "loaded"

    def test_data_file_status_missing_when_no_config(self):
        from fusion_health.api.routes.health import _data_file_status
        assert _data_file_status(None) == {}


# ---------- app lifespan ----------

class TestAppLifespan:
    def test_app_lifespan_starts_and_shuts(self):
        from fusion_health.api.app import create_app
        import fusion_health.api.gateway_provider as gp
        gp._shared_gateway = None
        cfg = HealthConfig()
        cfg.pubmed_enabled = False
        cfg.semantic_scholar_enabled = False
        app = create_app(cfg)
        from starlette.testclient import TestClient
        with TestClient(app) as c:
            resp = c.get("/api/v1/health")
            assert resp.status_code in (200, 503)
        # gateway lazy-created; if created, shutdown closes it
        assert gp._shared_gateway is None

    def test_close_gateway_runs_on_shutdown(self):
        from fusion_health.api.app import create_app
        import fusion_health.api.gateway_provider as gp
        gp._shared_gateway = None
        cfg = HealthConfig()
        cfg.pubmed_enabled = False
        cfg.semantic_scholar_enabled = False
        app = create_app(cfg)
        from starlette.testclient import TestClient
        with TestClient(app):
            # force lazy init
            g = gp.get_gateway(HealthConfig())
            assert gp._shared_gateway is g
        assert gp._shared_gateway is None


# ---------- enterprise readiness ----------

class TestEnterpriseReadiness:
    def test_check_flags_missing_keys(self, monkeypatch):
        from fusion_health.enterprise import production_readiness_check
        cfg = HealthConfig()
        for var in ("FUSION_HEALTH_API_KEY", "FUSION_HEALTH_AUDIT_HMAC_KEY",
                    "FUSION_HEALTH_PHI_KEY", "FUSION_HEALTH_CORS_ORIGINS"):
            monkeypatch.delenv(var, raising=False)
        failures = production_readiness_check(cfg)
        checks = {f["check"] for f in failures}
        assert "api_key" in checks
        assert "audit_hmac_key" in checks
        assert "phi_encryption" in checks
        assert "cors" in checks
        assert "data_source" in checks

    def test_check_passes_when_all_set(self, monkeypatch, tmp_path):
        from fusion_health.enterprise import production_readiness_check
        marker = tmp_path / ".data_source"
        marker.write_text("full")
        cfg = HealthConfig()
        cfg.data_dir = tmp_path
        monkeypatch.setenv("FUSION_HEALTH_API_KEY", "k1")
        monkeypatch.setenv("FUSION_HEALTH_AUDIT_HMAC_KEY", "k2")
        monkeypatch.setenv("FUSION_HEALTH_PHI_KEY", "aa" * 32)
        monkeypatch.setenv("FUSION_HEALTH_CORS_ORIGINS", "https://h.local")
        failures = production_readiness_check(cfg)
        assert failures == []

    def test_assert_off_mode_skips(self, monkeypatch):
        from fusion_health.enterprise import assert_enterprise_ready
        monkeypatch.delenv("FUSION_HEALTH_ENTERPRISE", raising=False)
        assert assert_enterprise_ready(HealthConfig()) is True

    def test_assert_enterprise_soft_warns(self, monkeypatch):
        from fusion_health.enterprise import assert_enterprise_ready
        monkeypatch.setenv("FUSION_HEALTH_ENTERPRISE", "1")
        monkeypatch.delenv("FUSION_HEALTH_ENTERPRISE_HARD", raising=False)
        for var in ("FUSION_HEALTH_API_KEY", "FUSION_HEALTH_AUDIT_HMAC_KEY",
                    "FUSION_HEALTH_PHI_KEY", "FUSION_HEALTH_CORS_ORIGINS"):
            monkeypatch.delenv(var, raising=False)
        assert assert_enterprise_ready(HealthConfig()) is False

    def test_assert_enterprise_hard_raises(self, monkeypatch):
        from fusion_health.enterprise import assert_enterprise_ready
        monkeypatch.setenv("FUSION_HEALTH_ENTERPRISE", "1")
        monkeypatch.setenv("FUSION_HEALTH_ENTERPRISE_HARD", "1")
        for var in ("FUSION_HEALTH_API_KEY", "FUSION_HEALTH_AUDIT_HMAC_KEY",
                    "FUSION_HEALTH_PHI_KEY", "FUSION_HEALTH_CORS_ORIGINS"):
            monkeypatch.delenv(var, raising=False)
        with pytest.raises(RuntimeError, match="Enterprise production readiness"):
            assert_enterprise_ready(HealthConfig())

    def test_assert_enterprise_pass_when_ready(self, monkeypatch, tmp_path):
        from fusion_health.enterprise import assert_enterprise_ready
        (tmp_path / ".data_source").write_text("full")
        cfg = HealthConfig()
        cfg.data_dir = tmp_path
        monkeypatch.setenv("FUSION_HEALTH_ENTERPRISE", "1")
        monkeypatch.setenv("FUSION_HEALTH_ENTERPRISE_HARD", "1")
        monkeypatch.setenv("FUSION_HEALTH_API_KEY", "k1")
        monkeypatch.setenv("FUSION_HEALTH_AUDIT_HMAC_KEY", "k2")
        monkeypatch.setenv("FUSION_HEALTH_PHI_KEY", "aa" * 32)
        monkeypatch.setenv("FUSION_HEALTH_CORS_ORIGINS", "https://h.local")
        assert assert_enterprise_ready(cfg) is True

    def test_health_ready_reports_enterprise_failures(self, monkeypatch):
        from fusion_health.api.app import create_app
        for var in ("FUSION_HEALTH_API_KEY", "FUSION_HEALTH_AUDIT_HMAC_KEY",
                    "FUSION_HEALTH_PHI_KEY", "FUSION_HEALTH_CORS_ORIGINS"):
            monkeypatch.delenv(var, raising=False)
        cfg = HealthConfig()
        cfg.pubmed_enabled = False
        cfg.semantic_scholar_enabled = False
        app = create_app(cfg)
        from starlette.testclient import TestClient
        with TestClient(app) as c:
            resp = c.get("/api/v1/health/ready")
            body = resp.json()
            assert "enterprise_ready" in body
            assert body["enterprise_ready"] is False
            assert isinstance(body["enterprise_failures"], list)
            assert len(body["enterprise_failures"]) > 0

    def test_disclaimer_header_on_all_responses(self):
        from fusion_health.api.app import create_app
        cfg = HealthConfig()
        cfg.pubmed_enabled = False
        cfg.semantic_scholar_enabled = False
        app = create_app(cfg)
        from starlette.testclient import TestClient
        with TestClient(app) as c:
            for path in ("/api/v1/health", "/api/v1/health/ready"):
                resp = c.get(path)
                assert "X-Fusion-Disclaimer" in resp.headers, f"missing disclaimer on {path}"
                assert "advisory-only" in resp.headers["X-Fusion-Disclaimer"]
                assert "not NMPA-registered" in resp.headers["X-Fusion-Disclaimer"]
