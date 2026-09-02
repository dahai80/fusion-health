from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_FIELD_BOUNDARY_RE = re.compile(r"[:：\s]")


def _field_present(text: str, field: str) -> bool:
    if not field:
        return True
    start = 0
    while True:
        pos = text.find(field, start)
        if pos == -1:
            return False
        after = pos + len(field)
        is_label_start = pos == 0 or text[pos - 1] in "\n\r"
        is_label_end = after >= len(text) or bool(_FIELD_BOUNDARY_RE.match(text[after]))
        if is_label_start or is_label_end:
            return True
        start = pos + 1


class RuleEngine:
    def __init__(self, rules_dir: Path | None = None):
        self.rules_dir = rules_dir or Path(__file__).parent / "rules"
        self._rules: list[dict] = []

    def load_rules(self):
        self._rules = []
        if not self.rules_dir.exists():
            logger.warning("Rules directory not found: %s", self.rules_dir)
            return
        for yaml_file in sorted(self.rules_dir.glob("*.yaml")):
            try:
                with open(yaml_file, encoding="utf-8") as f:
                    rule_set = yaml.safe_load(f) or {}
                for rule in rule_set.get("rules", []):
                    rule["_source"] = yaml_file.name
                    self._rules.append(rule)
                logger.debug("Loaded %d rules from %s", len(rule_set.get("rules", [])), yaml_file.name)
            except Exception as e:
                logger.error("Failed to load rules from %s: %s", yaml_file.name, e)
        logger.info("Loaded %d compliance rules from %s", len(self._rules), self.rules_dir)

    def check(self, text: str) -> list[dict[str, Any]]:
        if not self._rules:
            self.load_rules()
        results = []
        for rule in self._rules:
            result = self._evaluate_rule(rule, text)
            results.append(result)
        return results

    def _evaluate_rule(self, rule: dict, text: str) -> dict[str, Any]:
        rule_id = rule.get("id", "UNKNOWN")
        rule_type = rule.get("type", "keyword")

        if rule_type == "keyword":
            keywords = rule.get("keywords", [])
            found = [kw for kw in keywords if kw in text]
            status = "fail" if found else "pass"
            detail = f"Found keywords: {found}" if found else ""

        elif rule_type == "regex":
            pattern = rule.get("pattern", "")
            try:
                match = re.search(pattern, text)
                status = "fail" if match else "pass"
                detail = f"Matched: {match.group()}" if match else ""
            except re.error as e:
                status = "warning"
                detail = f"Regex error: {e}"

        elif rule_type == "required":
            required = rule.get("fields", [])
            missing = [f for f in required if not _field_present(text, f)]
            status = "fail" if missing else "pass"
            detail = f"Missing fields: {missing}" if missing else "All required fields present"

        else:
            status = "warning"
            detail = f"Unknown rule type: {rule_type}"

        return {
            "rule_id": rule_id,
            "rule_description": rule.get("description", ""),
            "status": status,
            "detail": detail,
            "severity": rule.get("severity", "info"),
        }
