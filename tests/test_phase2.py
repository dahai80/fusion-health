from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fusion_health.config import HealthConfig
from fusion_health.schemas.base import LLMResult, VerificationStatus
from fusion_health.insurance.cn_coding import ICD9CM3Validator, DRGHelper, InsuranceCatalogMatcher, CNMedicalCoder
from fusion_health.tcm.assistant import TCMAssistant
from fusion_health.ehr.fhir_mapper import FHIRMapper
from fusion_health.artifact_client import ArtifactClient
from fusion_health.plugins.health_tools import EHRSummaryTool, ICD10CodingTool, TCMSyndromeTool, ComplianceAuditTool


def _make_config():
    return HealthConfig(mlx_url="http://localhost:11434/v1", model="test-model")


def _llm_result(content="", parsed=None, error="", raw="", model="test-model"):
    return LLMResult(content=content, parsed=parsed, error=error, raw=raw, model=model)


class TestICD9CM3Validator:
    def test_validate_known_code(self):
        v = ICD9CM3Validator(config=_make_config())
        result = v.validate("47.0901")
        assert result["valid"] is True
        assert result["status"] == VerificationStatus.verified

    def test_validate_unknown_code(self):
        v = ICD9CM3Validator(config=_make_config())
        result = v.validate("99.9999")
        assert result["valid"] is False

    def test_search_keyword(self):
        v = ICD9CM3Validator(config=_make_config())
        results = v.search("阑尾")
        assert len(results) > 0


class TestDRGHelper:
    def test_suggest(self):
        d = DRGHelper(config=_make_config())
        results = d.suggest("阑尾切除")
        assert len(results) > 0
        assert results[0]["drg_code"] == "GR01"

    def test_suggest_no_match(self):
        d = DRGHelper(config=_make_config())
        results = d.suggest("不存在的内容xyz")
        assert len(results) == 0

    def test_get(self):
        d = DRGHelper(config=_make_config())
        result = d.get("GR01")
        assert result is not None
        assert result["drg_name"] == "阑尾切除术"


class TestInsuranceCatalogMatcher:
    def test_match_known(self):
        m = InsuranceCatalogMatcher(config=_make_config())
        result = m.match("I10")
        assert result["matched"] is True
        assert result["level"] == "甲类"

    def test_match_unknown_returns_self_pay(self):
        m = InsuranceCatalogMatcher(config=_make_config())
        result = m.match("Z99.99")
        assert result["matched"] is False
        assert result["level"] == "自费"

    def test_batch_match(self):
        m = InsuranceCatalogMatcher(config=_make_config())
        results = m.batch_match(["I10", "Z99.99"])
        assert len(results) == 2
        assert results[0]["matched"] is True
        assert results[1]["matched"] is False


class TestCNMedicalCoder:
    @pytest.mark.asyncio
    async def test_suggest_drg_local(self):
        coder = CNMedicalCoder(config=_make_config())
        result = await coder.suggest_drg("阑尾切除术")
        assert result["source"] == "local"
        assert len(result["results"]) > 0

    @pytest.mark.asyncio
    async def test_match_insurance_catalog(self):
        coder = CNMedicalCoder(config=_make_config())
        results = coder.match_insurance_catalog(["I10", "Z99.99"])
        assert len(results) == 2


class TestTCMAssistant:
    def test_identify_syndrome(self):
        tcm = TCMAssistant(config=_make_config())
        results = tcm.identify_syndrome("头痛眩晕面红目赤急躁易怒")
        assert len(results) > 0
        assert results[0]["syndrome_id"] == "肝阳上亢"

    def test_identify_syndrome_no_match(self):
        tcm = TCMAssistant(config=_make_config())
        results = tcm.identify_syndrome("没有任何匹配的症状xyz")
        assert len(results) == 0

    def test_recommend_formula(self):
        tcm = TCMAssistant(config=_make_config())
        results = tcm.recommend_formula("肝阳上亢")
        assert len(results) > 0
        assert results[0]["formula_id"] == "天麻钩藤饮"

    def test_check_contraindications_violation(self):
        tcm = TCMAssistant(config=_make_config())
        violations = tcm.check_contraindications(["甘草", "甘遂"])
        assert len(violations) > 0
        assert violations[0]["rule"] == "十八反"

    def test_check_contraindications_no_violation(self):
        tcm = TCMAssistant(config=_make_config())
        violations = tcm.check_contraindications(["人参", "白术"])
        assert len(violations) == 0

    def test_check_nineteen_dreads(self):
        tcm = TCMAssistant(config=_make_config())
        violations = tcm.check_contraindications(["人参", "五灵脂"])
        assert len(violations) > 0
        assert "十九畏" in violations[0]["rule"]

    @pytest.mark.asyncio
    async def test_analyze_local(self):
        tcm = TCMAssistant(config=_make_config())
        result = await tcm.analyze("头痛眩晕面红目赤")
        assert result["source"] == "local"
        assert "syndromes" in result
        assert "formulas" in result


class TestFHIRMapper:
    def test_map_vitals(self):
        mapper = FHIRMapper()
        bundle = mapper.map_vitals({"bp": "120/80", "hr": "72", "temp": "36.5"})
        assert bundle.resourceType == "Bundle"
        assert len(bundle.entry) == 3
        for entry in bundle.entry:
            assert entry["resource"]["resourceType"] == "Observation"

    def test_map_diagnosis(self):
        mapper = FHIRMapper()
        bundle = mapper.map_diagnosis([{"code": "I10", "description": "高血压"}])
        assert len(bundle.entry) == 1
        assert bundle.entry[0]["resource"]["resourceType"] == "Condition"
        assert bundle.entry[0]["resource"]["code"]["code"] == "I10"

    def test_map_procedure(self):
        mapper = FHIRMapper()
        bundle = mapper.map_procedure([{"code": "47.0901", "description": "阑尾切除术"}])
        assert len(bundle.entry) == 1
        assert bundle.entry[0]["resource"]["resourceType"] == "Procedure"

    def test_map_medication(self):
        mapper = FHIRMapper()
        bundle = mapper.map_medication([{"name": "阿司匹林", "code": "R02AC01"}])
        assert len(bundle.entry) == 1
        assert bundle.entry[0]["resource"]["resourceType"] == "MedicationRequest"

    def test_map_clinical_summary(self):
        mapper = FHIRMapper()
        bundle = mapper.map_clinical_summary({
            "vitals": {"bp": "120/80"},
            "diagnoses": [{"code": "I10", "description": "高血压"}],
            "procedures": [{"code": "36.0701", "description": "支架置入"}],
        })
        assert len(bundle.entry) >= 3
        condition_entries = [e for e in bundle.entry if e["resource"]["resourceType"] == "Condition"]
        assert len(condition_entries) >= 1
        assert condition_entries[0]["resource"]["code"]["code"] == "I10"

    def test_to_json(self):
        mapper = FHIRMapper()
        bundle = mapper.map_vitals({"hr": "72"})
        json_str = mapper.to_json(bundle)
        assert "Observation" in json_str
        assert "8867-4" in json_str


class TestArtifactClient:
    @pytest.mark.asyncio
    async def test_create_unavailable(self):
        client = ArtifactClient(config=_make_config())
        result = await client.create("session1", "test", "content")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_unavailable(self):
        client = ArtifactClient(config=_make_config())
        result = await client.list_artifacts("session1")
        assert result == [] or result == {"artifacts": []}

    @pytest.mark.asyncio
    async def test_create_success(self):
        client = ArtifactClient(config=_make_config())
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {"artifact_id": "art-1", "status": "created"}}
        mock_response.raise_for_status = MagicMock()
        mock_async_client = MagicMock()
        mock_async_client.post = AsyncMock(return_value=mock_response)
        mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
        mock_async_client.__aexit__ = AsyncMock(return_value=False)
        with patch("httpx.AsyncClient", return_value=mock_async_client):
            result = await client.create("session1", "test", "content")
            assert result is not None
            assert result["artifact_id"] == "art-1"

    @pytest.mark.asyncio
    async def test_list_success(self):
        client = ArtifactClient(config=_make_config())
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": [{"id": "art-1", "type": "note"}]}
        mock_response.raise_for_status = MagicMock()
        mock_async_client = MagicMock()
        mock_async_client.post = AsyncMock(return_value=mock_response)
        mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
        mock_async_client.__aexit__ = AsyncMock(return_value=False)
        with patch("httpx.AsyncClient", return_value=mock_async_client):
            result = await client.list_artifacts("session1")
            assert len(result) == 1
            assert result[0]["id"] == "art-1"


class TestHealthTools:
    @pytest.mark.asyncio
    async def test_ehr_summary_tool(self):
        tool = EHRSummaryTool()
        assert tool.name == "ehr_summary"
        with patch("fusion_health.ehr.processor.EHRProcessor.generate_summary",
                    AsyncMock(return_value={"summary": "test"})):
            result = await tool.execute(clinical_notes="patient has chest pain")
            assert "summary" in result

    @pytest.mark.asyncio
    async def test_icd10_tool(self):
        tool = ICD10CodingTool()
        assert tool.name == "icd10_cn_coding"
        with patch("fusion_health.insurance.cn_coding.LLMGateway") as MockGW:
            mock_gw = MagicMock()
            mock_result = MagicMock(content='{"codes": []}', error=None, parsed=None)
            mock_gw.chat = AsyncMock(return_value=mock_result)
            MockGW.return_value = mock_gw
            result = await tool.execute(diagnosis_text="hypertension")
            assert isinstance(result, dict) or isinstance(result, list)

    @pytest.mark.asyncio
    async def test_tcm_tool(self):
        tool = TCMSyndromeTool()
        assert tool.name == "tcm_syndrome"
        result = await tool.execute(symptoms="头痛眩晕")
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_compliance_tool(self):
        tool = ComplianceAuditTool()
        assert tool.name == "compliance_audit"
        with patch("fusion_health.compliance.checker.LLMGateway") as MockGW:
            mock_gw = MagicMock()
            mock_result = MagicMock(content="{}", error=None, parsed=None)
            mock_gw.chat = AsyncMock(return_value=mock_result)
            MockGW.return_value = mock_gw
            result = await tool.execute(clinical_note="test note")
            assert isinstance(result, dict)
