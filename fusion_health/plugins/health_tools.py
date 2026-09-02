from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_cached_config = None


def _get_config():
    global _cached_config
    if _cached_config is None:
        from ..config import HealthConfig
        _cached_config = HealthConfig.from_env()
    return _cached_config


class BaseHealthTool:
    name: str = ""
    description: str = ""
    parameters: dict = {}

    async def execute(self, **kwargs) -> dict[str, Any]:
        raise NotImplementedError


class EHRSummaryTool(BaseHealthTool):
    name = "ehr_summary"
    description = "生成结构化临床摘要"
    parameters = {
        "type": "object",
        "properties": {
            "clinical_notes": {"type": "string", "description": "临床笔记文本"},
        },
        "required": ["clinical_notes"],
    }

    async def execute(self, clinical_notes: str, **kwargs) -> dict[str, Any]:
        from ..ehr.processor import EHRProcessor
        config = _get_config()
        processor = EHRProcessor(config=config)
        return await processor.generate_summary(clinical_notes)


class ICD10CodingTool(BaseHealthTool):
    name = "icd10_cn_coding"
    description = "建议 ICD-10-CN 诊断编码（含数据库验证）"
    parameters = {
        "type": "object",
        "properties": {
            "diagnosis_text": {"type": "string", "description": "诊断文本"},
        },
        "required": ["diagnosis_text"],
    }

    async def execute(self, diagnosis_text: str, **kwargs) -> dict[str, Any]:
        from ..insurance.coder import InsuranceCoder
        config = _get_config()
        coder = InsuranceCoder(config=config)
        codes = await coder.suggest_icd_codes(diagnosis_text)
        return {"codes": codes}


class TCMSyndromeTool(BaseHealthTool):
    name = "tcm_syndrome"
    description = "中医证候辨识与方剂推荐"
    parameters = {
        "type": "object",
        "properties": {
            "symptoms": {"type": "string", "description": "症状描述"},
        },
        "required": ["symptoms"],
    }

    async def execute(self, symptoms: str, **kwargs) -> dict[str, Any]:
        from ..tcm.assistant import TCMAssistant
        config = _get_config()
        assistant = TCMAssistant(config=config)
        return await assistant.analyze(symptoms)


class ComplianceAuditTool(BaseHealthTool):
    name = "compliance_audit"
    description = "合规审计：规则引擎 + AI 分析"
    parameters = {
        "type": "object",
        "properties": {
            "clinical_note": {"type": "string", "description": "临床文档文本"},
        },
        "required": ["clinical_note"],
    }

    async def execute(self, clinical_note: str, **kwargs) -> dict[str, Any]:
        from ..compliance.checker import ComplianceChecker
        config = _get_config()
        checker = ComplianceChecker(config=config)
        return await checker.audit_documentation(clinical_note)


HEALTH_TOOLS = [EHRSummaryTool, ICD10CodingTool, TCMSyndromeTool, ComplianceAuditTool]
