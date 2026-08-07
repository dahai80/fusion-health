from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import os
os.environ.setdefault("FUSION_HEALTH_API_KEY", "test-key-123")

from fusion_health.config import HealthConfig
from fusion_health.conversation import ConversationMemory, ConversationSession
from fusion_health.templates import TemplateEngine
from fusion_health.batch import BatchProcessor


class TestConversationMemory:
    def test_start_session(self):
        mem = ConversationMemory()
        sid = mem.start_session("test-001")
        assert sid == "test-001"
        assert mem.session_id == "test-001"
        assert mem.turn_count == 0

    def test_add_messages(self):
        mem = ConversationMemory()
        mem.start_session()
        mem.add_system_message("You are a medical AI.")
        mem.add_user_message("Hello")
        mem.add_assistant_message("Hi, how can I help?")
        assert mem.turn_count == 1
        msgs = mem.get_messages()
        assert len(msgs) == 3
        assert msgs[0]["role"] == "system"

    def test_short_term_trim(self):
        mem = ConversationMemory()
        mem.start_session()
        for i in range(25):
            mem.add_user_message(f"msg {i}")
            mem.add_assistant_message(f"resp {i}")
        assert len(mem._short_term) <= 20

    def test_trim_preserves_system_message(self):
        mem = ConversationMemory()
        mem.start_session()
        mem.add_system_message("Critical system prompt")
        for i in range(25):
            mem.add_user_message(f"msg {i}")
            mem.add_assistant_message(f"resp {i}")
        roles = [m["role"] for m in mem._short_term]
        assert "system" in roles
        system_msgs = [m for m in mem._short_term if m["role"] == "system"]
        assert system_msgs[0]["content"] == "Critical system prompt"

    def test_save_load(self, tmp_path):
        mem = ConversationMemory()
        mem.start_session("save-test")
        mem.add_user_message("test input")
        mem.add_assistant_message("test output")
        fpath = tmp_path / "conv.json"
        mem.save(fpath)
        assert fpath.exists()

        mem2 = ConversationMemory()
        sid = mem2.load(fpath)
        assert sid == "save-test"
        assert mem2.turn_count == 1

    def test_clear_short_term(self):
        mem = ConversationMemory()
        mem.start_session()
        mem.add_user_message("hello")
        mem.clear_short_term()
        assert mem.turn_count == 0


class TestConversationSession:
    @patch("fusion_health.conversation.LLMGateway")
    def test_start_and_chat(self, MockGateway):
        mock_gw = MagicMock()
        mock_result = MagicMock()
        mock_result.content = "I can help with that."
        mock_result.error = ""
        mock_gw.chat = AsyncMock(return_value=mock_result)
        MockGateway.return_value = mock_gw

        cfg = HealthConfig()
        session = ConversationSession(cfg)
        sid = session.start("sess-1")
        assert sid == "sess-1"

        result = asyncio.run(session.chat("What is hypertension?"))
        assert result.content == "I can help with that."
        assert session.memory.turn_count == 1

    @patch("fusion_health.conversation.LLMGateway")
    def test_multi_turn(self, MockGateway):
        mock_gw = MagicMock()
        mock_gw.chat = AsyncMock(side_effect=[
            MagicMock(content="Response 1", error=""),
            MagicMock(content="Response 2", error=""),
        ])
        MockGateway.return_value = mock_gw

        cfg = HealthConfig()
        session = ConversationSession(cfg)
        session.start()

        asyncio.run(session.chat("Turn 1"))
        asyncio.run(session.chat("Turn 2"))
        assert session.memory.turn_count == 2
        assert len(mock_gw.chat.call_args_list) == 2


class TestTemplateEngine:
    def test_render_discharge_summary(self):
        cfg = HealthConfig()
        engine = TemplateEngine(cfg)
        result = engine.render("discharge_summary", {
            "patient_name": "张三",
            "diagnosis": "高血压",
            "hospital_course": "入院后予降压治疗",
        })
        assert "张三" in result
        assert "高血压" in result

    def test_render_claim_report(self):
        cfg = HealthConfig()
        engine = TemplateEngine(cfg)
        result = engine.render("claim_report", {
            "patient_name": "李四",
            "icd_codes": [{"code": "I10", "description": "高血压", "status": "verified"}],
        })
        assert "I10" in result
        assert "高血压" in result

    def test_render_compliance_report(self):
        cfg = HealthConfig()
        engine = TemplateEngine(cfg)
        result = engine.render("compliance_report", {
            "overall_compliant": False,
            "rules_checked": [
                {"rule_id": "PIPL-001", "rule_description": "身份证号检测", "status": "fail", "detail": "检测到身份证号"},
            ],
        })
        assert "不合规" in result
        assert "PIPL-001" in result

    def test_list_templates(self):
        cfg = HealthConfig()
        engine = TemplateEngine(cfg)
        templates = engine.list_templates()
        assert len(templates) >= 3

    def test_init_default_templates(self, tmp_path):
        TemplateEngine.init_default_templates(tmp_path)
        assert (tmp_path / "discharge_summary.j2").exists()
        assert (tmp_path / "claim_report.j2").exists()
        assert (tmp_path / "compliance_report.j2").exists()

    def test_render_missing_template(self):
        cfg = HealthConfig()
        engine = TemplateEngine(cfg)
        result = engine.render("nonexistent_template", {})
        assert "Error" in result

    def test_custom_template(self, tmp_path):
        (tmp_path / "custom.j2").write_text("Hello {{ name }}!", encoding="utf-8")
        cfg = HealthConfig()
        cfg.templates_dir = tmp_path
        engine = TemplateEngine(cfg)
        result = engine.render("custom", {"name": "World"})
        assert result == "Hello World!"


class TestBatchProcessor:
    @patch("fusion_health.batch.EHRProcessor")
    def test_process_directory(self, MockEHR):
        mock_proc = MagicMock()
        mock_proc.generate_summary = AsyncMock(return_value={"chief_complaint": "headache"})
        MockEHR.return_value = mock_proc

        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            (d / "case1.txt").write_text("Patient with headache", encoding="utf-8")
            (d / "case2.txt").write_text("Patient with chest pain", encoding="utf-8")

            cfg = HealthConfig()
            bp = BatchProcessor(cfg, max_concurrent=1)
            result = asyncio.run(
                bp.process_directory(d, "ehr_summary")
            )
            assert result["total"] == 2
            assert result["success"] == 2
            assert result["errors"] == 0

    @patch("fusion_health.batch.EHRProcessor")
    def test_process_with_output_dir(self, MockEHR):
        mock_proc = MagicMock()
        mock_proc.extract_vitals = AsyncMock(return_value={"bp": "120/80"})
        MockEHR.return_value = mock_proc

        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            out = d / "output"
            (d / "notes.txt").write_text("BP 120/80", encoding="utf-8")

            cfg = HealthConfig()
            bp = BatchProcessor(cfg)
            result = asyncio.run(
                bp.process_directory(d, "ehr_vitals", output_dir=out)
            )
            assert result["success"] == 1
            assert out.exists()

    def test_empty_directory(self, tmp_path):
        cfg = HealthConfig()
        bp = BatchProcessor(cfg)
        result = asyncio.run(
            bp.process_directory(tmp_path, "ehr_summary")
        )
        assert result["total"] == 0

    def test_unknown_action(self):
        cfg = HealthConfig()
        bp = BatchProcessor(cfg)
        with pytest.raises(ValueError, match="Unknown batch action"):
            asyncio.run(
                bp._execute_action("invalid_action", "text")
            )


class TestChatAPIRoutes:
    def test_chat_start(self):
        from fusion_health.api.app import create_app
        from starlette.testclient import TestClient
        app = create_app(HealthConfig())
        client = TestClient(app, headers={"X-API-Key": "test-key-123"})
        resp = client.post("/api/v1/chat/start", json={"session_id": "test-sess"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == "test-sess"

    @patch("fusion_health.conversation.LLMGateway")
    def test_chat_message(self, MockGateway):
        mock_gw = MagicMock()
        mock_result = MagicMock()
        mock_result.content = "Medical advice here"
        mock_result.error = ""
        mock_gw.chat = AsyncMock(return_value=mock_result)
        MockGateway.return_value = mock_gw

        from fusion_health.api.app import create_app
        from starlette.testclient import TestClient
        app = create_app(HealthConfig())
        client = TestClient(app, headers={"X-API-Key": "test-key-123"})

        client.post("/api/v1/chat/start", json={"session_id": "msg-test"})
        resp = client.post("/api/v1/chat/message", json={
            "session_id": "msg-test",
            "message": "What is hypertension?",
        })
        assert resp.status_code == 200

    def test_chat_message_missing_session(self):
        from fusion_health.api.app import create_app
        from starlette.testclient import TestClient
        app = create_app(HealthConfig())
        client = TestClient(app, headers={"X-API-Key": "test-key-123"})
        resp = client.post("/api/v1/chat/message", json={
            "session_id": "nonexistent",
            "message": "test",
        })
        assert resp.status_code == 200
        assert resp.json()["error"] == "session_not_found"

    def test_list_sessions(self):
        from fusion_health.api.app import create_app
        from starlette.testclient import TestClient
        app = create_app(HealthConfig())
        client = TestClient(app, headers={"X-API-Key": "test-key-123"})
        resp = client.get("/api/v1/chat/sessions")
        assert resp.status_code == 200
        assert "sessions" in resp.json()

    def test_delete_session(self):
        from fusion_health.api.app import create_app
        from starlette.testclient import TestClient
        app = create_app(HealthConfig())
        client = TestClient(app, headers={"X-API-Key": "test-key-123"})
        client.post("/api/v1/chat/start", json={"session_id": "del-test"})
        resp = client.delete("/api/v1/chat/sessions/del-test")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    def test_delete_nonexistent_session(self):
        from fusion_health.api.app import create_app
        from starlette.testclient import TestClient
        app = create_app(HealthConfig())
        client = TestClient(app, headers={"X-API-Key": "test-key-123"})
        resp = client.delete("/api/v1/chat/sessions/no-such-session")
        assert resp.status_code == 200
        assert resp.json()["error"] == "session_not_found"
