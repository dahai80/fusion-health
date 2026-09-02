from __future__ import annotations

import csv
import logging
from typing import Any

from ..config import HealthConfig
from ..schemas.base import VerificationStatus

logger = logging.getLogger(__name__)


class ICDValidator:
    _DB_CACHE: dict[str, dict[str, dict]] = {}

    def __init__(self, config: HealthConfig | None = None):
        self.config = config or HealthConfig.from_env()
        self._icd10_db = self._DB_CACHE.setdefault(str(self.config.data_dir), {})

    def _load(self):
        if self._icd10_db:
            return
        db_path = self.config.data_dir / "icd10_cn" / "icd10_cn.tsv"
        if not db_path.exists():
            logger.warning("ICD-10-CN database not found at %s", db_path)
            return
        try:
            with open(db_path, encoding="utf-8") as f:
                reader = csv.DictReader(f, delimiter="\t")
                for row in reader:
                    code = row.get("code", "").strip()
                    if code:
                        self._icd10_db[code] = row
            logger.info("Loaded %d ICD-10-CN codes from %s", len(self._icd10_db), db_path)
        except Exception as e:
            logger.error("Failed to load ICD-10-CN database: %s", e)

    def validate(self, code: str) -> dict[str, Any]:
        self._load()
        entry = self._icd10_db.get(code)
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
        for code, entry in self._icd10_db.items():
            desc = entry.get("description", "").lower()
            if keyword_lower in desc or keyword_lower in code:
                results.append({"code": code, **entry})
                if len(results) >= limit:
                    break
        return results

    def annotate_codes(self, codes: list[str]) -> list[dict[str, Any]]:
        annotated = []
        for code in codes:
            result = self.validate(code)
            annotated.append({"code": code, **result})
        return annotated
