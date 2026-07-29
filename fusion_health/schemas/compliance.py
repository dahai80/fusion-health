from __future__ import annotations

from pydantic import BaseModel


class ComplianceRuleResult(BaseModel):
    rule_id: str = ""
    rule_description: str = ""
    status: str = ""
    detail: str = ""
    severity: str = "info"
    ai_analysis: str = ""


class ComplianceAuditResult(BaseModel):
    overall_compliant: bool = False
    rules_checked: list[ComplianceRuleResult] = []
    error: str = ""
