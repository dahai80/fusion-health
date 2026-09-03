from __future__ import annotations

import asyncio
import os

import pytest

from fusion_health.config import HealthConfig
from fusion_health.ehr.processor import EHRProcessor
from fusion_health.insurance.coder import InsuranceCoder
from fusion_health.llm_gateway import LLMGateway

REAL_MODEL = os.getenv("FUSION_HEALTH_REAL_MODEL", "0") == "1"
MODEL = os.getenv("FUSION_HEALTH_MODEL", "Qwen3.8-27B-4bit")
MLX_URL = os.getenv("FUSION_HEALTH_MLX_URL", "http://localhost:11434/v1")
MLX_KEY = os.getenv("FUSION_MLX_API_KEY", "")

pytestmark = pytest.mark.skipif(
    not REAL_MODEL,
    reason="set FUSION_HEALTH_REAL_MODEL=1 (with fusion-mlx running) to run real-model regression",
)


def _cfg() -> HealthConfig:
    cfg = HealthConfig()
    cfg.model = MODEL
    cfg.mlx_url = MLX_URL
    cfg.mlx_route = "chat"
    if MLX_KEY:
        cfg.mlx_api_key = MLX_KEY
    cfg.pubmed_enabled = False
    cfg.semantic_scholar_enabled = False
    return cfg


def _backend_up() -> bool:
    import httpx
    try:
        r = httpx.get(f"{MLX_URL.rstrip('/')}/models", headers={"Authorization": f"Bearer {MLX_KEY}"} if MLX_KEY else {}, timeout=5.0)
        return r.status_code == 200
    except Exception:
        return False


@pytest.fixture(scope="module", autouse=True)
def _require_backend():
    if not _backend_up():
        pytest.skip("fusion-mlx backend not reachable at " + MLX_URL)


class TestRealModel:
    def test_ehr_summary_returns_content(self):
        cfg = _cfg()
        proc = EHRProcessor(cfg)
        notes = "Patient is a 65-year-old male with history of hypertension presenting with chest pain. BP 160/95. ECG shows ST elevation."
        result = asyncio.run(proc.generate_summary(notes))
        assert "error" not in result or result.get("error") is None, f"ehr error: {result.get('error')}"
        diagnosis = result.get("diagnosis") or result.get("summary") or result.get("raw") or ""
        assert diagnosis, f"empty diagnosis/summary: {result}"

    def test_icd10_coding_suggests_codes(self):
        cfg = _cfg()
        coder = InsuranceCoder(cfg)
        codes = asyncio.run(coder.suggest_icd_codes("hypertension and type 2 diabetes"))
        assert isinstance(codes, list)
        assert codes, "no codes suggested"

    def test_chat_roundtrip(self):
        cfg = _cfg()
        gw = LLMGateway(cfg)
        result = asyncio.run(gw.chat(messages=[{"role": "user", "content": "Say OK."}]))
        assert result.content, f"empty content, error={result.error}"
        assert not result.error

    def test_stream_yields_tokens(self):
        cfg = _cfg()
        gw = LLMGateway(cfg)

        async def collect():
            tokens = []
            async for t in gw.chat_stream(messages=[{"role": "user", "content": "Count from 1 to 3."}]):
                tokens.append(t)
            return tokens

        tokens = asyncio.run(collect())
        assert "".join(tokens), "stream produced no tokens"
