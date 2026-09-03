from __future__ import annotations

import asyncio
import os

import pytest

from fusion_health.clinical_eval import (
    GOLDEN_CASES,
    EvalResult,
    evaluate,
    format_report,
    score_case,
)


class _MockCoder:
    def __init__(self, mapping: dict[str, list[str]]):
        self.mapping = mapping

    async def suggest_icd_codes(self, text: str) -> list[str]:
        for key, codes in self.mapping.items():
            if key.lower() in text.lower():
                return codes
        return []


class TestScoreCase:
    def test_exact_hit(self):
        sc = score_case(["I10"], ["I10"])
        assert sc["hit"] is True
        assert sc["precision"] == 1.0
        assert sc["recall"] == 1.0

    def test_partial_recall(self):
        sc = score_case(["I10"], ["I10", "E11"])
        assert sc["hit"] is True
        assert sc["recall"] == 0.5

    def test_no_overlap(self):
        sc = score_case(["J45"], ["I10"])
        assert sc["hit"] is False
        assert sc["precision"] == 0.0

    def test_normalization(self):
        # I10.9 should match I10 at 3-char level
        sc = score_case(["I10.9"], ["I10"])
        assert sc["hit"] is True

    def test_empty_expected(self):
        sc = score_case(["I10"], [])
        assert sc["hit"] is False

    def test_empty_predicted(self):
        sc = score_case([], ["I10"])
        assert sc["hit"] is False
        assert sc["precision"] == 0.0


class TestEvaluate:
    def test_perfect_mock(self):
        mapping = {
            "hypertension": ["I10"],
            "type 2 diabetes": ["E11"],
            "appendicitis": ["K35"],
            "pneumonia": ["J18"],
            "asthma": ["J45"],
        }
        result = asyncio.run(evaluate(_MockCoder(mapping)))
        assert result.total == len(GOLDEN_CASES)
        assert result.recall == 1.0
        assert result.precision == 1.0
        assert result.f1 == 1.0
        assert all(c["hit"] for c in result.per_case)

    def test_partial_mock(self):
        mapping = {"hypertension": ["I10"], "diabetes": ["E11"]}
        result = asyncio.run(evaluate(_MockCoder(mapping)))
        assert result.total == len(GOLDEN_CASES)
        hits = sum(1 for c in result.per_case if c["hit"])
        assert hits == 2
        assert result.recall > 0
        assert result.recall < 1.0

    def test_empty_predictions(self):
        result = asyncio.run(evaluate(_MockCoder({})))
        assert result.with_any_code == 0
        assert result.recall == 0.0
        assert result.precision == 0.0

    def test_coder_exception_treated_as_empty(self):
        class _BrokenCoder:
            async def suggest_icd_codes(self, text):
                raise RuntimeError("boom")
        result = asyncio.run(evaluate(_BrokenCoder()))
        assert result.with_any_code == 0
        assert result.recall == 0.0

    def test_format_report_runs(self):
        result = EvalResult(total=2, with_any_code=2, precision=1.0, recall=1.0, f1=1.0,
                            per_case=[{"case_id": "x", "hit": True, "precision": 1.0, "recall": 1.0, "pred": ["I10"], "exp": ["I10"]}])
        report = format_report(result)
        assert "precision=1.00" in report
        assert "✓" in report


REAL_MODEL = os.getenv("FUSION_HEALTH_REAL_MODEL", "0") == "1"
MODEL = os.getenv("FUSION_HEALTH_MODEL", "Qwen3.8-27B-4bit")
MLX_URL = os.getenv("FUSION_HEALTH_MLX_URL", "http://localhost:11434/v1")
MLX_KEY = os.getenv("FUSION_MLX_API_KEY", "")


@pytest.mark.skipif(not REAL_MODEL, reason="set FUSION_HEALTH_REAL_MODEL=1 (fusion-mlx running) for real clinical eval")
class TestRealClinicalEval:
    def test_real_model_recall_above_threshold(self):
        import httpx
        try:
            r = httpx.get(f"{MLX_URL.rstrip('/')}/models",
                          headers={"Authorization": f"Bearer {MLX_KEY}"} if MLX_KEY else {}, timeout=5.0)
            if r.status_code != 200:
                pytest.skip("backend not up")
        except Exception:
            pytest.skip("backend not up")

        from fusion_health.config import HealthConfig
        from fusion_health.insurance.coder import InsuranceCoder

        cfg = HealthConfig()
        cfg.model = MODEL
        cfg.mlx_url = MLX_URL
        cfg.mlx_route = "chat"
        if MLX_KEY:
            cfg.mlx_api_key = MLX_KEY
        cfg.pubmed_enabled = False
        cfg.semantic_scholar_enabled = False
        coder = InsuranceCoder(cfg)
        result = asyncio.run(evaluate(coder))
        report = format_report(result)
        print(report)
        # lenient threshold for a small-LLM golden set — flags total failure, not perfection
        assert result.recall > 0.0, f"recall=0 — model returned no correct codes\n{report}"
