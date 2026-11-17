from __future__ import annotations

import os
from pathlib import Path

import pytest

REAL_HOME = Path(os.environ.get("HOME", str(Path.home()))).resolve()
REAL_DATA_DIR = REAL_HOME / ".fusion-health"

_ISOLATED_ENV_VARS = (
    "FUSION_HEALTH_LOG_DIR",
    "FUSION_HEALTH_AUDIT_LOG",
    "FUSION_HEALTH_AUDIT_HMAC_KEY",
    "FUSION_HEALTH_RATE_LIMIT_DB",
)


@pytest.fixture(autouse=True)
def _isolate_home(tmp_path, monkeypatch):
    fake_home = tmp_path / "test-session-home"
    fake_home.mkdir()
    fake_data_dir = fake_home / ".fusion-health"
    fake_data_dir.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("FUSION_HEALTH_LOG_DIR", str(fake_data_dir))
    monkeypatch.setenv("FUSION_HEALTH_AUDIT_LOG", str(fake_data_dir / "audit.log"))
    monkeypatch.setenv("FUSION_HEALTH_AUDIT_HMAC_KEY", "test-only-hmac-key")
    monkeypatch.setenv("FUSION_HEALTH_RATE_LIMIT_DB", str(fake_data_dir / "rate_limit.db"))
    yield


@pytest.fixture(autouse=True)
def _assert_no_real_home_writes(_isolate_home):
    from fusion_health.audit import _log_path
    from fusion_health.logging_config import _log_dir

    yield

    resolved = {
        "audit_log": str(Path(_log_path()).resolve()),
        "log_dir": str(Path(_log_dir()).resolve()),
    }
    for name, p in resolved.items():
        assert not p.startswith(str(REAL_DATA_DIR)), (
            f"{name} resolved into the real user data dir ({p}) — "
            "test HOME isolation broke, see tests/conftest.py"
        )
