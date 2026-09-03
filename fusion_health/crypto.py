from __future__ import annotations

import base64
import hashlib
import json
import logging
import os

logger = logging.getLogger(__name__)

ENC_VERSION = 1
_SALT_LEN = 16
_NONCE_LEN = 12
_KEY_LEN = 32
_PBKDF2_ITERS = 200_000


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, _PBKDF2_ITERS, dklen=_KEY_LEN)


def _resolve_key():
    raw = os.getenv("FUSION_HEALTH_PHI_KEY", "").strip()
    if not raw:
        return None
    if len(raw) == 64:
        try:
            return ("raw", bytes.fromhex(raw))
        except ValueError:
            pass
    return ("pass", raw)


def encryption_enabled() -> bool:
    return bool(os.getenv("FUSION_HEALTH_PHI_KEY", "").strip())


def _aes_key(salt: bytes) -> bytes:
    kind, val = _resolve_key()
    if kind == "raw":
        return val
    return _derive_key(val, salt)


def encrypt_json(data: dict) -> bytes:
    resolved = _resolve_key()
    if resolved is None:
        return json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    salt = os.urandom(_SALT_LEN)
    nonce = os.urandom(_NONCE_LEN)
    key = _aes_key(salt)
    ct = AESGCM(key).encrypt(nonce, json.dumps(data, ensure_ascii=False).encode("utf-8"), None)
    envelope = {
        "enc_version": ENC_VERSION,
        "mode": resolved[0],
        "salt": base64.b64encode(salt).decode("ascii"),
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ct).decode("ascii"),
    }
    logger.debug("Conversation encrypted (mode=%s)", resolved[0])
    return json.dumps(envelope, ensure_ascii=False).encode("utf-8")


def decrypt_bytes(raw: bytes) -> dict:
    text = raw.decode("utf-8", errors="replace")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"conversation file not valid JSON: {e}") from e
    if not isinstance(parsed, dict) or "enc_version" not in parsed:
        return parsed
    if parsed.get("enc_version") != ENC_VERSION:
        raise ValueError(f"unsupported enc_version: {parsed.get('enc_version')}")
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if _resolve_key() is None:
        raise ValueError("encrypted conversation file but FUSION_HEALTH_PHI_KEY not set")
    salt = base64.b64decode(parsed["salt"])
    nonce = base64.b64decode(parsed["nonce"])
    ct = base64.b64decode(parsed["ciphertext"])
    key = _aes_key(salt)
    plaintext = AESGCM(key).decrypt(nonce, ct, None)
    return json.loads(plaintext.decode("utf-8"))
