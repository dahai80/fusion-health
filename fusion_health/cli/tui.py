from __future__ import annotations

import json
import logging
from typing import Any

from rich.markdown import Markdown
from rich.panel import Panel
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, Footer, Header, Input, Static

from ..config import HealthConfig

logger = logging.getLogger(__name__)


MENU_ITEMS = [
    ("ehr_summary", "📋 EHR 临床摘要", "生成结构化临床摘要"),
    ("ehr_discharge", "🏥 出院小结", "生成出院小结"),
    ("ehr_vitals", "💉 生命体征", "提取生命体征数据"),
    ("code_icd10", "🔢 ICD-10 编码", "建议 ICD-10 诊断编码"),
    ("code_cpt", "💊 CPT 编码", "建议 CPT 操作编码"),
    ("code_audit", "📝 理赔审核", "审核保险理赔"),
    ("literature", "📚 文献检索", "检索临床文献"),
    ("compliance", "✅ 合规检查", "审核文档合规性"),
    ("tcm", "🌿 中医辅助", "辨证论治辅助"),
    ("drg", "🏷️  DRG 分组", "DRG 诊断分组建议"),
]


class ResultDisplay(Static):
    pass


class FusionHealthTUI(App):
    CSS = """
    #menu { width: 32; dock: left; border-right: solid green; }
    #menu Button { width: 100%; margin: 0 0 1 0; }
    #workspace { width: 1fr; }
    #input-area { dock: bottom; height: 5; border-top: solid green; }
    #input-box { width: 1fr; }
    #result-area { width: 100%; height: 1fr; }
    .result-panel { margin: 1 2; }
    """

    BINDINGS = [("q", "quit", "退出"), ("1", "focus_input", "输入")]

    def __init__(self, config: HealthConfig | None = None):
        super().__init__()
        self.config = config or HealthConfig.from_env()
        self._current_action: str = ""
        self._result_widget: ResultDisplay | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with VerticalScroll(id="menu"):
                for action_id, label, _ in MENU_ITEMS:
                    btn = Button(label, id=f"btn-{action_id}")
                    yield btn
            with Container(id="workspace"):
                yield ResultDisplay(id="result-area")
                with Horizontal(id="input-area"):
                    yield Input(placeholder="输入文本或文件路径...", id="input-box")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        if btn_id.startswith("btn-"):
            self._current_action = btn_id[4:]
            _, label, desc = next(
                (a, lbl, d) for a, lbl, d in MENU_ITEMS if a == self._current_action
            )
            result = self.query_one("#result-area", ResultDisplay)
            result.update(Panel(f"已选择: {label}\n{desc}\n\n在下方输入内容后按 Enter 执行", title="操作"))
            self.query_one("#input-box", Input).focus()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        if not value or not self._current_action:
            return
        event.input.value = ""
        result = self.query_one("#result-area", ResultDisplay)
        result.update(Panel("⏳ 处理中...", title="请稍候"))
        try:
            output = await self._execute_action(self._current_action, value)
            result.update(Panel(Markdown(f"```json\n{output}\n```"), title="结果"))
        except Exception as e:
            logger.error("TUI action error: %s", e)
            result.update(Panel(f"❌ 错误: {e}", title="错误"))

    async def _execute_action(self, action: str, text: str) -> str:
        if action == "ehr_summary":
            from ..ehr.processor import EHRProcessor
            proc = EHRProcessor(self.config)
            result = await proc.generate_summary(text)
            return _format_json(result)

        elif action == "ehr_discharge":
            from ..ehr.processor import EHRProcessor
            proc = EHRProcessor(self.config)
            result = await proc.generate_discharge_summary(text, "", "")
            return str(result)

        elif action == "ehr_vitals":
            from ..ehr.processor import EHRProcessor
            proc = EHRProcessor(self.config)
            result = await proc.extract_vitals(text)
            return _format_json(result)

        elif action == "code_icd10":
            from ..insurance.coder import InsuranceCoder
            coder = InsuranceCoder(self.config)
            result = await coder.suggest_icd_codes(text)
            return _format_json(result)

        elif action == "code_cpt":
            from ..insurance.coder import InsuranceCoder
            coder = InsuranceCoder(self.config)
            result = await coder.suggest_cpt_codes(text)
            return _format_json(result)

        elif action == "code_audit":
            from ..insurance.coder import InsuranceCoder
            coder = InsuranceCoder(self.config)
            result = await coder.audit_claim({"text": text})
            return _format_json(result)

        elif action == "literature":
            from ..literature.retriever import LiteratureRetriever
            ret = LiteratureRetriever(self.config)
            results = await ret.search(text)
            return _format_json(results)

        elif action == "compliance":
            from ..compliance.checker import ComplianceChecker
            cc = ComplianceChecker(self.config)
            result = await cc.audit_documentation(text)
            return _format_json(result)

        elif action == "tcm":
            from ..tcm.assistant import TCMAssistant
            assistant = TCMAssistant(self.config)
            result = await assistant.analyze(text)
            return _format_json(result)

        elif action == "drg":
            from ..insurance.cn_coding import CNMedicalCoder
            coder = CNMedicalCoder(self.config)
            result = await coder.suggest_drg(text)
            return _format_json(result)

        return "未知操作"

    def action_focus_input(self) -> None:
        self.query_one("#input-box", Input).focus()


def _format_json(data: Any) -> str:
    try:
        return json.dumps(data, indent=2, ensure_ascii=False)
    except Exception:
        return str(data)


def run_tui(config: HealthConfig | None = None):
    app = FusionHealthTUI(config)
    app.run()
