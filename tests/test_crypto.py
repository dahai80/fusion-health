from __future__ import annotations

import os
from pathlib import Path

import pytest

from fusion_health import crypto
from fusion_health.config import HealthConfig
from fusion_health.conversation import ConversationSession


@pytest.fixture(autouse=True)
def _clear_phi_key():
    saved = os.environ.get("FUSION_HEALTH_PHI_KEY")
    yield
    if saved is None:
        os.environ.pop("FUSION_HEALTH_PHI_KEY", None)
    else:
        os.environ["FUSION_HEALTH_PHI_KEY"] = saved


class TestCrypto:
    def test_plaintext_when_no_key(self):
        os.environ.pop("FUSION_HEALTH_PHI_KEY", None)
        assert crypto.encryption_enabled() is False
        data = {"session_id": "s1", "short_term": [{"role": "user", "content": "hi"}]}
        out = crypto.encrypt_json(data)
        assert b"short_term" in out
        assert crypto.decrypt_bytes(out) == data

    def test_encrypt_decrypt_raw_key(self):
        os.environ["FUSION_HEALTH_PHI_KEY"] = "aa" * 32
        assert crypto.encryption_enabled() is True
        data = {"session_id": "s2", "short_term": [{"role": "user", "content": "PHI secret"}]}
        out = crypto.encrypt_json(data)
        assert b"PHI secret" not in out
        assert b"enc_version" in out
        assert crypto.decrypt_bytes(out) == data

    def test_encrypt_decrypt_passphrase(self):
        os.environ["FUSION_HEALTH_PHI_KEY"] = "a-passphrase"
        data = {"session_id": "s3", "short_term": [{"role": "user", "content": "secret"}]}
        out = crypto.encrypt_json(data)
        assert b"secret" not in out
        assert crypto.decrypt_bytes(out) == data

    def test_decrypt_without_key_fails(self):
        os.environ["FUSION_HEALTH_PHI_KEY"] = "bb" * 32
        out = crypto.encrypt_json({"session_id": "s4"})
        os.environ.pop("FUSION_HEALTH_PHI_KEY", None)
        with pytest.raises(ValueError, match="FUSION_HEALTH_PHI_KEY"):
            crypto.decrypt_bytes(out)

    def test_wrong_key_fails(self):
        os.environ["FUSION_HEALTH_PHI_KEY"] = "cc" * 32
        out = crypto.encrypt_json({"session_id": "s5"})
        os.environ["FUSION_HEALTH_PHI_KEY"] = "dd" * 32
        with pytest.raises(Exception):
            crypto.decrypt_bytes(out)


class TestConversationEncryption:
    def test_save_load_encrypted_roundtrip(self, monkeypatch, tmp_path):
        os.environ["FUSION_HEALTH_PHI_KEY"] = "ee" * 32
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: fake_home)
        cfg = HealthConfig()
        sess = ConversationSession(cfg)
        sess.start("enc-sess")
        sess.memory.add_user_message("patient has fever")
        sess.save()
        path = cfg.literature_cache_dir.parent / "conversations" / "enc-sess.json"
        assert path.exists()
        raw = path.read_bytes()
        assert b"fever" not in raw
        assert b"enc_version" in raw

        sess2 = ConversationSession(cfg)
        sid = sess2.load(path)
        assert sid == "enc-sess"
        msgs = sess2.memory.get_messages()
        assert any("fever" in m["content"] for m in msgs)

    def test_save_load_plaintext_compat(self, monkeypatch, tmp_path):
        os.environ.pop("FUSION_HEALTH_PHI_KEY", None)
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: fake_home)
        cfg = HealthConfig()
        sess = ConversationSession(cfg)
        sess.start("plain-sess")
        sess.memory.add_user_message("plaintext note")
        sess.save()
        path = cfg.literature_cache_dir.parent / "conversations" / "plain-sess.json"
        raw = path.read_bytes()
        assert b"plaintext note" in raw
        sess2 = ConversationSession(cfg)
        sess2.load(path)
        assert any("plaintext note" in m["content"] for m in sess2.memory.get_messages())
