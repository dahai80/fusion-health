from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import HealthConfig

logger = logging.getLogger(__name__)

BUILTIN_TEMPLATES = {
    "discharge_summary": """# 出院小结

## 患者信息
- 姓名：{{ patient_name | default("未填写") }}
- 住院号：{{ admission_id | default("未填写") }}
- 入院日期：{{ admission_date | default("未填写") }}
- 出院日期：{{ discharge_date | default("未填写") }}

## 诊断
{{ diagnosis | default("未填写") }}

## 住院经过
{{ hospital_course | default("未填写") }}

## 出院医嘱
{{ discharge_meds | default("未填写") }}

## 随访计划
{{ follow_up | default("未填写") }}
""",
    "claim_report": """# 理赔审核报告

## 理赔信息
- 被保险人：{{ patient_name | default("未填写") }}
- 保单号：{{ policy_number | default("未填写") }}
- 理赔日期：{{ claim_date | default("未填写") }}

## 诊断编码
{% for code in icd_codes | default([]) %}
- {{ code.code }}: {{ code.description }} ({{ code.status }})
{% endfor %}

## 审核结果
{% for issue in issues | default([]) %}
- [{{ issue.severity | default("info") }}] {{ issue.detail | default("") }}
{% endfor %}

## 结论
{{ conclusion | default("审核完成") }}
""",
    "compliance_report": """# 合规审核报告

## 审核日期：{{ audit_date | default("今日") }}
## 文档类型：{{ document_type | default("临床文档") }}

## 规则检查结果
{% for rule in rules_checked | default([]) %}
- [{{ rule.status | upper }}] {{ rule.rule_id }}: {{ rule.rule_description }}
  {% if rule.detail %}详情：{{ rule.detail }}{% endif %}
{% endfor %}

## 总体结论
{% if overall_compliant %}✅ 合规{% else %}❌ 不合规{% endif %}
""",
}


class TemplateEngine:
    def __init__(self, config: HealthConfig | None = None):
        self.config = config or HealthConfig.from_env()
        self._env: Environment | None = None
        self._templates_dir = self.config.templates_dir

    def _get_env(self) -> Environment:
        if self._env is not None:
            return self._env

        search_paths = []
        if self._templates_dir.exists():
            search_paths.append(str(self._templates_dir))

        builtin_dir = Path(__file__).parent / "templates"
        builtin_dir.mkdir(parents=True, exist_ok=True)
        for name, content in BUILTIN_TEMPLATES.items():
            tpath = builtin_dir / f"{name}.j2"
            if not tpath.exists():
                tpath.write_text(content, encoding="utf-8")
                logger.info("Created builtin template: %s", tpath.name)

        search_paths.append(str(builtin_dir))
        self._env = Environment(
            loader=FileSystemLoader(search_paths),
            autoescape=select_autoescape(default=False),
        )
        return self._env

    def render(self, template_name: str, context: dict[str, Any]) -> str:
        env = self._get_env()
        try:
            if not template_name.endswith(".j2"):
                template_name = f"{template_name}.j2"
            template = env.get_template(template_name)
            result = template.render(**context)
            logger.info("Rendered template: %s, len=%d", template_name, len(result))
            return result
        except Exception as e:
            logger.error("Template render error: %s — %s", template_name, e)
            return f"[Template Error: {e}]"

    def list_templates(self) -> list[str]:
        env = self._get_env()
        return sorted(env.list_templates())

    @staticmethod
    def init_default_templates(templates_dir: Path | None = None):
        if templates_dir is None:
            templates_dir = Path.home() / ".fusion-health" / "templates"
        templates_dir.mkdir(parents=True, exist_ok=True)
        for name, content in BUILTIN_TEMPLATES.items():
            tpath = templates_dir / f"{name}.j2"
            if not tpath.exists():
                tpath.write_text(content, encoding="utf-8")
                logger.info("Created default template: %s", tpath)
