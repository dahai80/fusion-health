from __future__ import annotations

import os
import subprocess
import textwrap
from pathlib import Path

import pytest

START_SH = Path(__file__).resolve().parent.parent / "start.sh"

REGISTERED_YAML = """\
services:
  fusion-simulation-metrics:
    port: 11456
    purpose: other
  fusion-health:
    port: 11469
    purpose: health
    boot: T2
    fixed: false
"""


def _run_registry_check(tmp_path: Path, registry_text: str | None, port: str = "11469", extra_env: dict | None = None):
    registry = tmp_path / "port-registry.yaml"
    if registry_text is not None:
        registry.write_text(registry_text, encoding="utf-8")
    env = {**os.environ, "FUSION_REGISTRY": str(registry)}
    env.update(extra_env or {})
    script = textwrap.dedent(f"""
        set -u
        source "{START_SH}"
        PORT="{port}"
        check_port_registry
    """)
    return subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True)


class TestPortRegistryCheck:
    def test_passes_when_registered(self, tmp_path):
        r = _run_registry_check(tmp_path, REGISTERED_YAML)
        assert r.returncode == 0, r.stderr
        assert "refusing" not in r.stdout + r.stderr

    def test_refuses_when_port_missing(self, tmp_path):
        r = _run_registry_check(tmp_path, REGISTERED_YAML, port="12345")
        assert r.returncode == 1
        assert "not registered" in r.stdout + r.stderr
        assert "refusing to start" in r.stdout + r.stderr

    def test_refuses_when_service_missing(self, tmp_path):
        yaml_no_health = "services:\n  fusion-other:\n    port: 11469\n    purpose: other\n"
        r = _run_registry_check(tmp_path, yaml_no_health)
        assert r.returncode == 1
        assert "refusing to start" in r.stdout + r.stderr

    def test_bypass_env_skips_refusal(self, tmp_path):
        r = _run_registry_check(tmp_path, REGISTERED_YAML, port="12345",
                                extra_env={"FUSION_SKIP_REGISTRY_CHECK": "1"})
        assert r.returncode == 0
        assert "registry check bypassed" in r.stdout + r.stderr

    def test_missing_registry_file_warns_and_continues(self, tmp_path):
        r = _run_registry_check(tmp_path, None)
        assert r.returncode == 0
        assert "registry self-check skipped" in r.stdout + r.stderr

    def test_start_refuses_unregistered_port_live(self, tmp_path):
        if (Path(__file__).resolve().parent.parent / ".fusion-health.pid").exists():
            pytest.skip("service running — pid file present, do_start short-circuits")
        registry = tmp_path / "port-registry.yaml"
        registry.write_text("services:\n  fusion-other:\n    port: 1\n", encoding="utf-8")
        env = {**os.environ, "FUSION_REGISTRY": str(registry), "FUSION_HEALTH_PORT": "12345"}
        r = subprocess.run(["bash", str(START_SH), "start"], env=env, capture_output=True, text=True)
        assert r.returncode != 0
        assert "refusing to start" in (r.stdout + r.stderr)
