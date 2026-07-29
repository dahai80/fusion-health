from __future__ import annotations

import logging
from typing import Any

from ..config import HealthConfig
from ..llm_gateway import LLMGateway
from ..schemas.compliance import ComplianceAuditResult, ComplianceRuleResult
from .rule_engine import RuleEngine

logger = logging.getLogger(__name__)


class ComplianceChecker:
    def __init__(self, config: HealthConfig | None = None, mlx_url: str | None = None):
        if config is None:
            config = HealthConfig.from_env()
        if mlx_url is not None:
            config.mlx_url = mlx_url
        self.config = config
        self._gateway = LLMGateway(config)
        self._rule_engine = RuleEngine(config.rules_dir)

    async def audit_documentation(self, clinical_note: str) -> dict[str, Any]:
        rule_results = self._rule_engine.check(clinical_note)
        rule_failures = [r for r in rule_results if r["status"] == "fail"]

        llm_result = await self._gateway.chat(
            messages=[{"role": "user", "content": (
                f"Audit this clinical note for: 1) completeness, 2) missing elements, "
                f"3) coding accuracy, 4) regulatory compliance. "
                f"Return as JSON: {{'overall_compliant': bool, 'rules_checked': [{{'rule_id': str, 'rule_description': str, 'status': 'pass|fail', 'detail': str}}]}}\n\n{clinical_note[:4000]}"
            )}],
            max_tokens=2048,
            response_schema=ComplianceAuditResult,
        )

        combined_rules = []
        for r in rule_results:
            combined_rules.append(ComplianceRuleResult(
                rule_id=r["rule_id"],
                rule_description=r["rule_description"],
                status=r["status"],
                detail=r["detail"],
                severity=r.get("severity", "info"),
            ))

        if llm_result.parsed:
            for r in llm_result.parsed.rules_checked:
                combined_rules.append(r)
            overall = llm_result.parsed.overall_compliant and len(rule_failures) == 0
        else:
            overall = len(rule_failures) == 0
            if llm_result.error:
                logger.warning("LLM audit fallback, using rule engine only: %s", llm_result.error)

        return ComplianceAuditResult(
            overall_compliant=overall,
            rules_checked=combined_rules,
            error="",
        ).model_dump()

    async def check_regulatory_compliance(self, document_type: str, content: str) -> dict[str, Any]:
        rule_results = self._rule_engine.check(content)
        rule_failures = [r for r in rule_results if r["status"] == "fail"]

        llm_result = await self._gateway.chat(
            messages=[{"role": "user", "content": (
                f"Check this {document_type} for regulatory compliance. "
                f"Identify any compliance gaps or risks. "
                f"Return as JSON: {{'overall_compliant': bool, 'rules_checked': [{{'rule_id': str, 'rule_description': str, 'status': 'pass|fail', 'detail': str}}]}}\n\n{content[:3000]}"
            )}],
            max_tokens=2048,
            response_schema=ComplianceAuditResult,
        )

        combined_rules = []
        for r in rule_results:
            combined_rules.append(ComplianceRuleResult(
                rule_id=r["rule_id"],
                rule_description=r["rule_description"],
                status=r["status"],
                detail=r["detail"],
                severity=r.get("severity", "info"),
            ))

        if llm_result.parsed:
            for r in llm_result.parsed.rules_checked:
                combined_rules.append(r)
            overall = llm_result.parsed.overall_compliant and len(rule_failures) == 0
        else:
            overall = len(rule_failures) == 0
            if llm_result.error:
                logger.warning("LLM regulatory check fallback, using rule engine only: %s", llm_result.error)

        return ComplianceAuditResult(
            overall_compliant=overall,
            rules_checked=combined_rules,
            error="",
        ).model_dump()
