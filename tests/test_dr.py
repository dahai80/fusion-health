from __future__ import annotations

import sys
import tarfile
from pathlib import Path

import pytest

from fusion_health import audit


@pytest.fixture
def audit_env(tmp_path, monkeypatch):
    log = tmp_path / "audit.log"
    monkeypatch.setenv("FUSION_HEALTH_AUDIT_LOG", str(log))
    monkeypatch.setenv("FUSION_HEALTH_AUDIT_HMAC_KEY", "test-hmac-key")
    audit._seq = 0
    return log


class TestAuditIntegrity:
    def test_verify_log_file_ok(self, audit_env):
        audit.log_access("owner1", "GET", "/ehr", "read", "200", "phi text")
        audit.log_access("owner1", "POST", "/code", "code", "200", "phi2")
        ok, tampered = audit.verify_log_file(audit_env)
        assert ok == 2
        assert tampered == 0

    def test_verify_log_file_detects_tamper(self, audit_env):
        audit.log_access("owner1", "GET", "/ehr", "read", "200", "phi")
        # tamper: rewrite a line with a forged signature
        lines = audit_env.read_text().splitlines()
        body, _ = lines[0].rsplit("\t", 1)
        audit_env.write_text(f"{body}\tdeadbeefdeadbeefdeadbeefdeadbeef\n", encoding="utf-8")
        ok, tampered = audit.verify_log_file(audit_env)
        assert tampered == 1
        assert ok == 0

    def test_verify_log_file_detects_seq_gap(self, audit_env):
        audit.log_access("o", "GET", "/x", "r", "200")
        audit.log_access("o", "GET", "/y", "r", "200")
        # inject a line with seq 5 (gap after 2)
        import json
        event = {"seq": 5, "ts": "2026-01-01T00:00:00+00:00", "owner_id": "o",
                 "method": "GET", "path": "/z", "action": "r", "status": "200",
                 "phi_input_hash": "", "phi_input_len": 0}
        body = json.dumps(event, ensure_ascii=False, sort_keys=True)
        sig = audit._hmac(body)
        with open(audit_env, "a", encoding="utf-8") as f:
            f.write(f"{body}\t{sig}\n")
        ok, tampered = audit.verify_log_file(audit_env)
        assert tampered == 1

    def test_verify_missing_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("FUSION_HEALTH_AUDIT_LOG", str(tmp_path / "nope.log"))
        ok, tampered = audit.verify_log_file()
        assert ok == 0 and tampered == 0


class TestAuditRotation:
    def test_no_rotation_when_small(self, audit_env):
        audit.log_access("o", "GET", "/x", "r", "200")
        result = audit.rotate_log(max_bytes=10 * 1024 * 1024)
        assert result is None
        assert audit_env.exists()

    def test_rotates_when_large(self, audit_env):
        audit.log_access("o", "GET", "/x", "r", "200")
        # pad the file past threshold
        with open(audit_env, "a", encoding="utf-8") as f:
            f.write("x" * 1024)
        archive = audit.rotate_log(max_bytes=512, keep=3)
        assert archive is not None
        assert archive.exists()
        assert archive.name == "audit.log.1"
        # rotate recreates an empty log so subsequent writes resume
        assert audit_env.exists()
        assert audit_env.stat().st_size == 0

    def test_rotation_keep_limit(self, audit_env):
        for _ in range(3):
            audit.log_access("o", "GET", "/x", "r", "200")
            with open(audit_env, "a", encoding="utf-8") as f:
                f.write("x" * 1024)
            audit.rotate_log(max_bytes=512, keep=2)
        archives = sorted((audit_env.parent).glob("audit.log.*"))
        # keep=2 means at most 2 archives
        assert len(archives) <= 2


class TestBackupRestore:
    def test_backup_and_verify_roundtrip(self, tmp_path, monkeypatch):
        # stage audit log + a session file
        log = tmp_path / "audit.log"
        monkeypatch.setenv("FUSION_HEALTH_AUDIT_LOG", str(log))
        monkeypatch.setenv("FUSION_HEALTH_AUDIT_HMAC_KEY", "bk-key")
        monkeypatch.setenv("FUSION_HEALTH_HOME", str(tmp_path / "fh-home"))
        audit._seq = 0
        audit.log_access("o", "GET", "/ehr", "read", "200", "phi")

        conv = tmp_path / "fh-home" / "conversations"
        conv.mkdir(parents=True)
        (conv / "sess-1.json").write_text('{"session_id":"s1","short_term":[]}')

        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        try:
            import importlib
            if "backup" in sys.modules:
                backup_mod = importlib.reload(sys.modules["backup"])
            else:
                backup_mod = importlib.import_module("backup")
            out = tmp_path / "bkout"
            archive = backup_mod.backup(out, verify=True)
            assert archive.exists()
            assert tarfile.is_tarfile(archive)
            rc = backup_mod.restore(archive)
            assert rc == 0
        finally:
            sys.path.pop(0)

    def test_backup_aborts_on_tampered_audit(self, tmp_path, monkeypatch):
        log = tmp_path / "audit.log"
        monkeypatch.setenv("FUSION_HEALTH_AUDIT_LOG", str(log))
        monkeypatch.setenv("FUSION_HEALTH_AUDIT_HMAC_KEY", "bk-key")
        monkeypatch.setenv("FUSION_HEALTH_HOME", str(tmp_path / "fh-home"))
        audit._seq = 0
        audit.log_access("o", "GET", "/x", "r", "200")
        # tamper
        lines = log.read_text().splitlines()
        body, _ = lines[0].rsplit("\t", 1)
        log.write_text(f"{body}\t00\n", encoding="utf-8")

        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        try:
            import importlib
            if "backup" in sys.modules:
                backup_mod = importlib.reload(sys.modules["backup"])
            else:
                backup_mod = importlib.import_module("backup")
            out = tmp_path / "bkout2"
            with pytest.raises(SystemExit) as exc:
                backup_mod.backup(out, verify=True)
            assert exc.value.code == 3
        finally:
            sys.path.pop(0)
