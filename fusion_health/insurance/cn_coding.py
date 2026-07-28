from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any

from ..config import HealthConfig
from ..llm_gateway import LLMGateway
from ..schemas.base import VerificationStatus

logger = logging.getLogger(__name__)


class ICD9CM3Validator:
    def __init__(self, config: HealthConfig | None = None):
        self.config = config or HealthConfig.from_env()
        self._db: dict[str, dict] = {}
        self._loaded = False

    def _load(self):
        if self._loaded:
            return
        db_path = self.config.data_dir / "icd9cm3_cn" / "icd9cm3_cn.tsv"
        if not db_path.exists():
            logger.warning("ICD-9-CM-3 CN database not found at %s", db_path)
            self._loaded = True
            return
        try:
            with open(db_path, encoding="utf-8") as f:
                reader = csv.DictReader(f, delimiter="\t")
                for row in reader:
                    code = row.get("code", "").strip()
                    if code:
                        self._db[code] = row
            logger.info("Loaded %d ICD-9-CM-3 CN codes", len(self._db))
        except Exception as e:
            logger.error("Failed to load ICD-9-CM-3 CN: %s", e)
        self._loaded = True

    def validate(self, code: str) -> dict[str, Any]:
        self._load()
        entry = self._db.get(code)
        if entry:
            return {
                "valid": True,
                "description": entry.get("description", ""),
                "category": entry.get("category", ""),
                "status": VerificationStatus.verified,
            }
        return {"valid": False, "description": "", "category": "", "status": VerificationStatus.unverified}

    def search(self, keyword: str, limit: int = 10) -> list[dict]:
        self._load()
        results = []
        keyword_lower = keyword.lower()
        for code, entry in self._db.items():
            desc = entry.get("description", "").lower()
            if keyword_lower in desc or keyword_lower in code:
                results.append({"code": code, **entry})
                if len(results) >= limit:
                    break
        return results


class DRGHelper:
    def __init__(self, config: HealthConfig | None = None):
        self.config = config or HealthConfig.from_env()
        self._db: dict[str, dict] = {}
        self._loaded = False

    def _load(self):
        if self._loaded:
            return
        db_path = self.config.data_dir / "drg" / "drg_cn.tsv"
        if not db_path.exists():
            logger.warning("DRG database not found at %s", db_path)
            self._loaded = True
            return
        try:
            with open(db_path, encoding="utf-8") as f:
                reader = csv.DictReader(f, delimiter="\t")
                for row in reader:
                    code = row.get("drg_code", "").strip()
                    if code:
                        self._db[code] = row
            logger.info("Loaded %d DRG groups", len(self._db))
        except Exception as e:
            logger.error("Failed to load DRG database: %s", e)
        self._loaded = True

    def suggest(self, diagnosis_or_procedure: str, limit: int = 5) -> list[dict]:
        self._load()
        results = []
        keyword = diagnosis_or_procedure.lower()
        for drg_code, entry in self._db.items():
            name = entry.get("drg_name", "").lower()
            if keyword in name:
                results.append({"drg_code": drg_code, **entry})
                if len(results) >= limit:
                    break
        return results

    def get(self, drg_code: str) -> dict[str, Any] | None:
        self._load()
        entry = self._db.get(drg_code)
        if entry:
            return {"drg_code": drg_code, **entry}
        return None


class InsuranceCatalogMatcher:
    def __init__(self, config: HealthConfig | None = None):
        self.config = config or HealthConfig.from_env()
        self._db: dict[str, dict] = {}
        self._loaded = False

    def _load(self):
        if self._loaded:
            return
        db_path = self.config.data_dir / "insurance_catalog.tsv"
        if not db_path.exists():
            logger.warning("Insurance catalog not found at %s", db_path)
            self._loaded = True
            return
        try:
            with open(db_path, encoding="utf-8") as f:
                reader = csv.DictReader(f, delimiter="\t")
                for row in reader:
                    code = row.get("code", "").strip()
                    if code:
                        self._db[code] = row
            logger.info("Loaded %d insurance catalog entries", len(self._db))
        except Exception as e:
            logger.error("Failed to load insurance catalog: %s", e)
        self._loaded = True

    def match(self, icd_code: str) -> dict[str, Any]:
        self._load()
        entry = self._db.get(icd_code)
        if entry:
            return {
                "matched": True,
                "code": icd_code,
                "name": entry.get("name", ""),
                "level": entry.get("level", "自费"),
                "category": entry.get("category", ""),
            }
        return {"matched": False, "code": icd_code, "level": "自费", "name": "", "category": ""}

    def batch_match(self, icd_codes: list[str]) -> list[dict[str, Any]]:
        return [self.match(code) for code in icd_codes]


class CNMedicalCoder:
    def __init__(self, config: HealthConfig | None = None):
        self.config = config or HealthConfig.from_env()
        self._gateway = LLMGateway(config)
        self._icd9cm3 = ICD9CM3Validator(config)
        self._drg = DRGHelper(config)
        self._catalog = InsuranceCatalogMatcher(config)

    async def suggest_procedure_codes(self, procedure_text: str) -> list[dict[str, Any]]:
        result = await self._gateway.chat(
            messages=[{"role": "user", "content": (
                f"Suggest ICD-9-CM-3 procedure codes for: {procedure_text[:2000]}\n"
                f"Return as JSON: {{'codes': [{{'code': '47.0901', 'description': '...'}}]}}"
            )}],
            max_tokens=1024,
        )
        if result.error:
            logger.error("suggest_procedure_codes error: %s", result.error)
            return []
        codes = []
        try:
            data = {}
            if result.content:
                import json
                text = result.content.strip()
                if text.startswith("```"):
                    lines = text.split("\n")
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].strip() == "```":
                        lines = lines[:-1]
                    text = "\n".join(lines)
                data = json.loads(text)
            if not isinstance(data, dict):
                data = {}
            for item in data.get("codes", []):
                code = item.get("code", "")
                validation = self._icd9cm3.validate(code)
                item["status"] = validation["status"]
                if validation["valid"]:
                    item["description"] = validation["description"] or item.get("description", "")
                codes.append(item)
        except Exception as e:
            logger.error("Failed to parse procedure codes: %s", e)
        return codes

    async def suggest_drg(self, diagnosis_or_procedure: str) -> dict[str, Any]:
        local_results = self._drg.suggest(diagnosis_or_procedure)
        if local_results:
            return {"source": "local", "results": local_results}
        result = await self._gateway.chat(
            messages=[{"role": "user", "content": (
                f"Suggest DRG group for: {diagnosis_or_procedure[:2000]}\n"
                f"Return as JSON: {{'drg_code': str, 'drg_name': str, 'mdc': str, 'category': str}}"
            )}],
            max_tokens=512,
        )
        if result.error:
            logger.error("suggest_drg error: %s", result.error)
            return {"source": "ai", "results": []}
        try:
            data = {}
            if result.content:
                import json
                text = result.content.strip()
                if text.startswith("```"):
                    lines = text.split("\n")
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].strip() == "```":
                        lines = lines[:-1]
                    text = "\n".join(lines)
                data = json.loads(text)
            if not isinstance(data, dict):
                return {"source": "ai", "results": [], "raw": result.content}
            return {"source": "ai", "results": [data]}
        except Exception:
            return {"source": "ai", "results": [], "raw": result.content}

    def match_insurance_catalog(self, icd_codes: list[str]) -> list[dict[str, Any]]:
        return self._catalog.batch_match(icd_codes)
