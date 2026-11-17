from __future__ import annotations

import os
from pathlib import Path

from conftest import REAL_DATA_DIR, REAL_HOME

from fusion_health.audit import _log_path
from fusion_health.config import HealthConfig
from fusion_health.logging_config import _log_dir


def test_home_points_at_tmp_not_real(tmp_path):
    home = Path.home().resolve()
    assert home == Path(os.environ["HOME"]).resolve()
    assert home.is_relative_to(tmp_path.resolve())
    assert home != REAL_HOME


def test_audit_log_resolution_under_tmp(tmp_path):
    p = _log_path().resolve()
    assert p.is_relative_to(tmp_path.resolve())
    assert not str(p).startswith(str(REAL_DATA_DIR))


def test_logging_dir_resolution_under_tmp(tmp_path):
    d = _log_dir().resolve()
    assert d.is_relative_to(tmp_path.resolve())
    assert not str(d).startswith(str(REAL_DATA_DIR))


def test_conversation_save_dir_under_tmp(tmp_path):
    cfg = HealthConfig()
    save_dir = (cfg.literature_cache_dir.parent / "conversations").resolve()
    assert save_dir.is_relative_to(tmp_path.resolve())
    assert not str(save_dir).startswith(str(REAL_DATA_DIR))


def test_app_boot_does_not_touch_real_data_dir(tmp_path):
    from fastapi.testclient import TestClient

    from fusion_health.api.app import create_app

    real_app_log = REAL_DATA_DIR / "app.log"
    real_audit_log = REAL_DATA_DIR / "audit.log"
    before = {
        p: p.stat().st_size if p.exists() else None
        for p in (real_app_log, real_audit_log)
    }

    app = create_app(HealthConfig())
    with TestClient(app) as client:
        client.get("/api/v1/health")

    for p, size_before in before.items():
        size_after = p.stat().st_size if p.exists() else None
        assert size_after == size_before, (
            f"app boot wrote into real {p} — HOME isolation broke"
        )


def test_audit_key_not_empty_in_tests():
    assert os.environ.get("FUSION_HEALTH_AUDIT_HMAC_KEY", "") == "test-only-hmac-key"
