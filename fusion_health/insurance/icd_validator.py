from __future__ import annotations

import csv
import logging
import re
from typing import Any

from ..config import HealthConfig
from ..schemas.base import VerificationStatus

logger = logging.getLogger(__name__)

ICD10_FORMAT_RE = re.compile(r"^[A-Z]\d{2}(\.[A-Z0-9]{1,7})?$")

DEFAULT_DATA_SOURCE = "sample"


def _data_source(data_dir) -> str:
    marker = data_dir / ".data_source"
    try:
        if marker.exists():
            val = marker.read_text(encoding="utf-8").strip().lower()
            return val or DEFAULT_DATA_SOURCE
    except OSError:
        pass
    return DEFAULT_DATA_SOURCE


class ICDValidator:
    _DB_CACHE: dict[str, dict[str, Any]] = {}

    def __init__(self, config: HealthConfig | None = None):
        self.config = config or HealthConfig.from_env()
        cache_key = str(self.config.data_dir)
        self._icd10_db = self._DB_CACHE.setdefault(cache_key, {"codes": {}, "mtime": -1.0})

    def _load(self):
        db_path = self.config.data_dir / "icd10_cn" / "icd10_cn.tsv"
        try:
            mtime = db_path.stat().st_mtime if db_path.exists() else -1.0
        except OSError:
            mtime = -1.0
        if self._icd10_db.get("codes") and self._icd10_db.get("mtime") == mtime:
            return
        if not db_path.exists():
            logger.warning("ICD-10-CN database not found at %s", db_path)
            return
        try:
            codes: dict[str, dict] = {}
            with open(db_path, encoding="utf-8") as f:
                reader = csv.DictReader(f, delimiter="\t")
                for row in reader:
                    code = row.get("code", "").strip()
                    if code:
                        codes[code] = row
            self._icd10_db["codes"] = codes
            self._icd10_db["mtime"] = mtime
            logger.info("Loaded %d ICD-10-CN codes from %s (mtime=%s)", len(codes), db_path, mtime)
        except Exception as e:
            logger.error("Failed to load ICD-10-CN database: %s", e)

    def validate(self, code: str) -> dict[str, Any]:
        self._load()
        src = _data_source(self.config.data_dir)
        entry = self._icd10_db["codes"].get(code)
        if entry:
            return {
                "valid": True,
                "description": entry.get("description", ""),
                "category": entry.get("category", ""),
                "status": VerificationStatus.verified,
                "data_source": src,
            }
        if ICD10_FORMAT_RE.match(code):
            return {"valid": False, "description": "", "category": "", "status": VerificationStatus.unverified, "data_source": src}
        logger.warning("ICD-10 code invalid format: %s", code)
        return {"valid": False, "description": "", "category": "", "status": VerificationStatus.invalid, "data_source": src}

    def search(self, keyword: str, limit: int = 10) -> list[dict]:
        self._load()
        results = []
        keyword_lower = keyword.lower()
        for code, entry in self._icd10_db["codes"].items():
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
