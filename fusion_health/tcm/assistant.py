from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from ..config import HealthConfig
from ..llm_gateway import LLMGateway

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data"


class TCMAssistant:
    def __init__(self, config: HealthConfig | None = None):
        self.config = config or HealthConfig.from_env()
        self._gateway = LLMGateway(self.config)
        self._syndromes: list[dict] = []
        self._formulas: list[dict] = []
        self._contraindications: dict[str, list[dict]] = {}
        self._loaded = False

    def _load(self):
        if self._loaded:
            return
        try:
            with open(DATA_DIR / "syndromes.yaml", encoding="utf-8") as f:
                self._syndromes = (yaml.safe_load(f) or {}).get("syndromes", [])
            with open(DATA_DIR / "formulas.yaml", encoding="utf-8") as f:
                self._formulas = (yaml.safe_load(f) or {}).get("formulas", [])
            with open(DATA_DIR / "contraindications.yaml", encoding="utf-8") as f:
                self._contraindications = yaml.safe_load(f) or {}
            logger.info("Loaded %d syndromes, %d formulas", len(self._syndromes), len(self._formulas))
        except Exception as e:
            logger.error("Failed to load TCM data: %s", e)
        self._loaded = True

    def identify_syndrome(self, symptoms: str) -> list[dict[str, Any]]:
        self._load()
        results = []
        for syndrome in self._syndromes:
            matched = [s for s in syndrome.get("symptoms", []) if s in symptoms]
            if matched:
                total = len(syndrome.get("symptoms", []))
                score = len(matched) / total if total > 0 else 0.0
                results.append({
                    "syndrome_id": syndrome["id"],
                    "name": syndrome["name"],
                    "gb_code": syndrome.get("gb_code", ""),
                    "matched_symptoms": matched,
                    "score": round(score, 2),
                    "description": syndrome.get("description", ""),
                })
        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    def recommend_formula(self, syndrome_id: str) -> list[dict[str, Any]]:
        self._load()
        results = []
        for formula in self._formulas:
            if formula.get("syndrome") == syndrome_id:
                results.append({
                    "formula_id": formula["id"],
                    "syndrome": formula["syndrome"],
                    "herbs": formula.get("herbs", []),
                    "source": formula.get("source", ""),
                })
        return results

    def check_contraindications(self, herbs: list[str]) -> list[dict[str, Any]]:
        self._load()
        violations = []
        oppositions = self._contraindications.get("eighteen_oppositions", [])
        dreads = self._contraindications.get("nineteen_mutual_dreads", [])
        all_rules = oppositions + dreads
        for rule in all_rules:
            a, b = rule.get("herb_a", ""), rule.get("herb_b", "")
            if a in herbs and b in herbs:
                violations.append({
                    "herb_a": a,
                    "herb_b": b,
                    "rule": rule.get("rule", ""),
                    "severity": "critical",
                    "message": f"{a}与{b}属于{rule.get('rule', '')}，禁止同用",
                })
        return violations

    async def analyze(self, symptoms: str) -> dict[str, Any]:
        local_matches = self.identify_syndrome(symptoms)
        if local_matches:
            best = local_matches[0]
            formulas = self.recommend_formula(best["syndrome_id"])
            all_herbs = []
            for f in formulas:
                all_herbs.extend(f.get("herbs", []))
            contraindications = self.check_contraindications(all_herbs)
            return {
                "source": "local",
                "syndromes": local_matches,
                "formulas": formulas,
                "contraindications": contraindications,
            }

        result = await self._gateway.chat(
            messages=[{"role": "user", "content": (
                f"根据以下症状辨识中医证型并推荐方剂：{symptoms[:2000]}\n"
                f"返回JSON: {{'syndrome': str, 'formula': str, 'herbs': [str], 'reasoning': str}}"
            )}],
            max_tokens=1024,
        )
        if result.error:
            logger.error("TCM analyze error: %s", result.error)
            return {"source": "ai", "error": result.error}
        return {"source": "ai", "raw": result.content}
