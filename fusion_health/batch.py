from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from .config import HealthConfig
from .ehr.processor import EHRProcessor
from .insurance.coder import InsuranceCoder
from .compliance.checker import ComplianceChecker
from .tcm.assistant import TCMAssistant

logger = logging.getLogger(__name__)

ACTION_MAP = {
    "ehr_summary": "generate_summary",
    "ehr_vitals": "extract_vitals",
    "code_icd10": "suggest_icd_codes",
    "compliance_audit": "audit_documentation",
    "tcm_analyze": "analyze",
}


class BatchProcessor:
    def __init__(self, config: HealthConfig | None = None, max_concurrent: int = 3):
        self.config = config or HealthConfig.from_env()
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def process_directory(
        self, directory: Path, action: str, pattern: str = "*.txt", output_dir: Path | None = None,
    ) -> dict[str, Any]:
        files = sorted(directory.glob(pattern))
        if not files:
            logger.warning("No files matching '%s' in %s", pattern, directory)
            return {"total": 0, "success": 0, "errors": 0, "results": []}

        results: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        tasks = [self._process_file(f, action, output_dir, results, errors) for f in files]
        await asyncio.gather(*tasks)

        summary = {
            "total": len(files),
            "success": len(results),
            "errors": len(errors),
            "results": results,
        }
        if errors:
            summary["error_details"] = errors
        return summary

    async def _process_file(
        self,
        filepath: Path,
        action: str,
        output_dir: Path | None,
        results: list[dict[str, Any]],
        errors: list[dict[str, Any]],
    ):
        async with self._semaphore:
            try:
                text = await asyncio.to_thread(
                    filepath.read_text, encoding="utf-8", errors="replace"
                )
                result = await self._execute_action(action, text)
                results.append({"file": str(filepath), "status": "ok", "result": result})
                logger.info("Batch processed: %s [%s]", filepath.name, action)

                if output_dir:
                    out_path = output_dir / f"{filepath.stem}_{action}.json"
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    await asyncio.to_thread(
                        self._write_output, out_path, result,
                    )
            except Exception as e:
                logger.error("Batch error: %s — %s", filepath, e)
                errors.append({"file": str(filepath), "error": str(e)})

    @staticmethod
    def _write_output(out_path: Path, result: Any):
        out_path.write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8",
        )

    async def _execute_action(self, action: str, text: str) -> Any:
        if action == "ehr_summary":
            proc = EHRProcessor(self.config)
            return await proc.generate_summary(text)
        elif action == "ehr_vitals":
            proc = EHRProcessor(self.config)
            return await proc.extract_vitals(text)
        elif action == "code_icd10":
            coder = InsuranceCoder(self.config)
            return await coder.suggest_icd_codes(text)
        elif action == "compliance_audit":
            cc = ComplianceChecker(self.config)
            return await cc.audit_documentation(text)
        elif action == "tcm_analyze":
            assistant = TCMAssistant(self.config)
            return await assistant.analyze(text)
        else:
            raise ValueError(f"Unknown batch action: {action}")
