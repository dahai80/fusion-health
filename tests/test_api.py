from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from fusion_health.config import HealthConfig
from fusion_health.api.app import create_app


@pytest.fixture
def app():
    cfg = HealthConfig()
    cfg.pubmed_enabled = False
    cfg.semantic_scholar_enabled = False
    return create_app(cfg)


@pytest.fixture
def client(app):
    from starlette.testclient import TestClient
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_check(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "fusion-health"
        assert data["version"] == "0.2.0"

    def test_health_check_model(self, client):
        resp = client.get("/api/v1/health")
        data = resp.json()
        assert data["model"] == "qwen3.5-9b"


class TestEHREndpoints:
    @patch("fusion_health.ehr.processor.LLMGateway")
    def test_summary(self, MockGateway, client):
        mock_gw = MagicMock()
        mock_result = MagicMock()
        mock_result.parsed = None
        mock_result.error = None
        mock_result.content = '{"chief_complaint": "headache"}'
        mock_gw.chat = AsyncMock(return_value=mock_result)
        MockGateway.return_value = mock_gw

        resp = client.post("/api/v1/ehr/summary", json={"clinical_notes": "Patient presents with headache"})
        assert resp.status_code == 200

    @patch("fusion_health.ehr.processor.LLMGateway")
    def test_discharge(self, MockGateway, client):
        mock_gw = MagicMock()
        mock_result = MagicMock()
        mock_result.parsed = None
        mock_result.error = None
        mock_result.content = "Discharge summary text"
        mock_gw.chat = AsyncMock(return_value=mock_result)
        MockGateway.return_value = mock_gw

        resp = client.post("/api/v1/ehr/discharge", json={
            "admission_notes": "Admitted for chest pain",
            "progress_notes": "Improving",
            "discharge_meds": "Aspirin 81mg",
        })
        assert resp.status_code == 200
        assert "discharge_summary" in resp.json()

    @patch("fusion_health.ehr.processor.LLMGateway")
    def test_vitals(self, MockGateway, client):
        mock_gw = MagicMock()
        mock_result = MagicMock()
        mock_result.parsed = None
        mock_result.error = None
        mock_result.content = '{"bp": "120/80"}'
        mock_gw.chat = AsyncMock(return_value=mock_result)
        MockGateway.return_value = mock_gw

        resp = client.post("/api/v1/ehr/vitals", json={"text": "BP 120/80, HR 72"})
        assert resp.status_code == 200

    def test_summary_validation_empty(self, client):
        resp = client.post("/api/v1/ehr/summary", json={"clinical_notes": ""})
        assert resp.status_code == 422


class TestInsuranceEndpoints:
    @patch("fusion_health.insurance.coder.LLMGateway")
    def test_icd10(self, MockGateway, client):
        mock_gw = MagicMock()
        mock_result = MagicMock()
        mock_result.parsed = None
        mock_result.error = None
        mock_result.content = "[]"
        mock_gw.chat = AsyncMock(return_value=mock_result)
        MockGateway.return_value = mock_gw

        resp = client.post("/api/v1/insurance/icd10", json={"diagnosis_text": "hypertension"})
        assert resp.status_code == 200

    @patch("fusion_health.insurance.coder.LLMGateway")
    def test_cpt(self, MockGateway, client):
        mock_gw = MagicMock()
        mock_result = MagicMock()
        mock_result.parsed = None
        mock_result.error = None
        mock_result.content = "[]"
        mock_gw.chat = AsyncMock(return_value=mock_result)
        MockGateway.return_value = mock_gw

        resp = client.post("/api/v1/insurance/cpt", json={"procedure_text": "office visit"})
        assert resp.status_code == 200

    @patch("fusion_health.insurance.coder.LLMGateway")
    def test_claim_audit(self, MockGateway, client):
        mock_gw = MagicMock()
        mock_result = MagicMock()
        mock_result.parsed = None
        mock_result.error = None
        mock_result.content = "{}"
        mock_gw.chat = AsyncMock(return_value=mock_result)
        MockGateway.return_value = mock_gw

        resp = client.post("/api/v1/insurance/claim-audit", json={"claim_data": {"patient": "test"}})
        assert resp.status_code == 200

    def test_catalog(self, client):
        resp = client.post("/api/v1/insurance/catalog", json={"icd_codes": ["I10"]})
        assert resp.status_code == 200

    def test_drg(self, client):
        resp = client.post("/api/v1/insurance/drg", json={"diagnosis_or_procedure": "阑尾切除术"})
        assert resp.status_code == 200


class TestLiteratureEndpoints:
    @patch("fusion_health.literature.retriever.LLMGateway")
    def test_search(self, MockGateway, client):
        mock_gw = MagicMock()
        mock_result = MagicMock()
        mock_result.parsed = None
        mock_result.error = None
        mock_result.content = "[]"
        mock_gw.chat = AsyncMock(return_value=mock_result)
        MockGateway.return_value = mock_gw

        resp = client.post("/api/v1/literature/search", json={"query": "diabetes treatment"})
        assert resp.status_code == 200

    @patch("fusion_health.literature.retriever.LLMGateway")
    def test_evidence(self, MockGateway, client):
        mock_gw = MagicMock()
        mock_result = MagicMock()
        mock_result.parsed = None
        mock_result.error = None
        mock_result.content = "Evidence summary"
        mock_gw.chat = AsyncMock(return_value=mock_result)
        MockGateway.return_value = mock_gw

        resp = client.post("/api/v1/literature/evidence", json={
            "topic": "diabetes",
            "literature": [],
        })
        assert resp.status_code == 200

    def test_search_validation(self, client):
        resp = client.post("/api/v1/literature/search", json={"query": ""})
        assert resp.status_code == 422


class TestComplianceEndpoints:
    @patch("fusion_health.compliance.checker.LLMGateway")
    def test_audit(self, MockGateway, client):
        mock_gw = MagicMock()
        mock_result = MagicMock()
        mock_result.parsed = None
        mock_result.error = None
        mock_result.content = "{}"
        mock_gw.chat = AsyncMock(return_value=mock_result)
        MockGateway.return_value = mock_gw

        resp = client.post("/api/v1/compliance/audit", json={"clinical_note": "Patient seen today"})
        assert resp.status_code == 200

    @patch("fusion_health.compliance.checker.LLMGateway")
    def test_regulatory(self, MockGateway, client):
        mock_gw = MagicMock()
        mock_result = MagicMock()
        mock_result.parsed = None
        mock_result.error = None
        mock_result.content = "{}"
        mock_gw.chat = AsyncMock(return_value=mock_result)
        MockGateway.return_value = mock_gw

        resp = client.post("/api/v1/compliance/regulatory", json={
            "document_type": "discharge_summary",
            "content": "Patient discharged in stable condition",
        })
        assert resp.status_code == 200


class TestTCMEndpoints:
    def test_syndrome(self, client):
        resp = client.post("/api/v1/tcm/syndrome", json={"symptoms": "头痛 眩晕 面红"})
        assert resp.status_code == 200
        data = resp.json()
        assert "syndromes" in data

    def test_formula(self, client):
        resp = client.post("/api/v1/tcm/formula", json={"syndrome_id": "S01"})
        assert resp.status_code == 200
        data = resp.json()
        assert "formulas" in data

    def test_contraindications(self, client):
        resp = client.post("/api/v1/tcm/contraindications", json={"herbs": ["人参", "藜芦"]})
        assert resp.status_code == 200
        data = resp.json()
        assert "violations" in data

    @patch("fusion_health.tcm.assistant.LLMGateway")
    def test_analyze(self, MockGateway, client):
        resp = client.post("/api/v1/tcm/analyze", json={"symptoms": "头痛 眩晕 面红"})
        assert resp.status_code == 200


class TestAPIKeyMiddleware:
    def test_no_key_required_by_default(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200

    def test_health_exempt_with_key(self, app):
        import os
        os.environ["FUSION_HEALTH_API_KEY"] = "test-key-123"
        try:
            from starlette.testclient import TestClient
            c = TestClient(app)
            resp = c.get("/api/v1/health")
            assert resp.status_code == 200
        finally:
            del os.environ["FUSION_HEALTH_API_KEY"]

    def test_api_key_enforcement(self, app):
        import os
        os.environ["FUSION_HEALTH_API_KEY"] = "test-key-123"
        try:
            from starlette.testclient import TestClient
            c = TestClient(app)
            resp = c.post("/api/v1/ehr/summary", json={"clinical_notes": "test"})
            assert resp.status_code == 401
        finally:
            del os.environ["FUSION_HEALTH_API_KEY"]

    def test_api_key_header_accepted(self, app):
        import os
        os.environ["FUSION_HEALTH_API_KEY"] = "test-key-123"
        try:
            from starlette.testclient import TestClient
            c = TestClient(app)
            resp = c.post(
                "/api/v1/ehr/summary",
                json={"clinical_notes": "test"},
                headers={"X-API-Key": "test-key-123"},
            )
            assert resp.status_code in (200, 500)
        finally:
            del os.environ["FUSION_HEALTH_API_KEY"]


class TestSSEStreamEndpoints:
    @patch("fusion_health.api.routes.ehr.LLMGateway")
    def test_ehr_summary_stream(self, MockGateway, client):
        async def fake_stream(*args, **kwargs):
            for t in ["Hello", " world"]:
                yield t
        mock_gw = MagicMock()
        mock_gw.chat_stream = fake_stream
        MockGateway.return_value = mock_gw
        resp = client.post("/api/v1/ehr/summary/stream", json={"clinical_notes": "test notes"})
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

    @patch("fusion_health.api.routes.insurance.LLMGateway")
    def test_icd10_stream(self, MockGateway, client):
        async def fake_stream(*args, **kwargs):
            for t in ["A01", ": Typhoid"]:
                yield t
        mock_gw = MagicMock()
        mock_gw.chat_stream = fake_stream
        MockGateway.return_value = mock_gw
        resp = client.post("/api/v1/insurance/icd10/stream", json={"diagnosis_text": "fever"})
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

    @patch("fusion_health.api.routes.literature.LLMGateway")
    def test_evidence_stream(self, MockGateway, client):
        async def fake_stream(*args, **kwargs):
            yield "Evidence summary"
        mock_gw = MagicMock()
        mock_gw.chat_stream = fake_stream
        MockGateway.return_value = mock_gw
        resp = client.post("/api/v1/literature/evidence/stream", json={"topic": "diabetes"})
        assert resp.status_code == 200

    @patch("fusion_health.api.routes.compliance.LLMGateway")
    def test_audit_stream(self, MockGateway, client):
        async def fake_stream(*args, **kwargs):
            yield "Compliant"
        mock_gw = MagicMock()
        mock_gw.chat_stream = fake_stream
        MockGateway.return_value = mock_gw
        resp = client.post("/api/v1/compliance/audit/stream", json={"clinical_note": "note"})
        assert resp.status_code == 200

    @patch("fusion_health.api.routes.tcm.LLMGateway")
    def test_tcm_analyze_stream(self, MockGateway, client):
        async def fake_stream(*args, **kwargs):
            yield "肝郁气滞"
        mock_gw = MagicMock()
        mock_gw.chat_stream = fake_stream
        MockGateway.return_value = mock_gw
        resp = client.post("/api/v1/tcm/analyze/stream", json={"symptoms": "头痛"})
        assert resp.status_code == 200

    def test_chat_message_stream_no_session(self, client):
        resp = client.post("/api/v1/chat/message/stream", json={
            "session_id": "no-such", "message": "hi",
        })
        assert resp.status_code == 404

    @patch("fusion_health.api.routes.chat.LLMGateway")
    def test_chat_message_stream(self, MockGateway, client):
        async def fake_stream(*args, **kwargs):
            yield "Medical"
            yield " advice"
        mock_gw = MagicMock()
        mock_gw.chat_stream = fake_stream
        MockGateway.return_value = mock_gw
        client.post("/api/v1/chat/start", json={"session_id": "s-stream"})
        resp = client.post("/api/v1/chat/message/stream", json={
            "session_id": "s-stream", "message": "hello",
        })
        assert resp.status_code == 200
