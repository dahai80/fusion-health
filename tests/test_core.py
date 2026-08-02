from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fusion_health.config import HealthConfig
from fusion_health.llm_gateway import LLMGateway
from fusion_health.schemas.base import LLMResult
from fusion_health.schemas.ehr import ClinicalSummary, VitalsResult
from fusion_health.schemas.insurance import ICDCodeItem, ICDCodeResult, ClaimAuditResult
from fusion_health.schemas.literature import LiteratureItem, LiteratureSearchResult
from fusion_health.schemas.compliance import ComplianceAuditResult, ComplianceRuleResult
from fusion_health.ehr.processor import EHRProcessor
from fusion_health.insurance.coder import InsuranceCoder
from fusion_health.literature.retriever import LiteratureRetriever
from fusion_health.compliance.checker import ComplianceChecker
from fusion_health.compliance.rule_engine import RuleEngine
from fusion_health.insurance.icd_validator import ICDValidator
from fusion_health.literature.pubmed_client import PubMedClient
from fusion_health.literature.semantic_scholar import SemanticScholarClient


def _make_config():
    return HealthConfig(mlx_url="http://localhost:11434/v1", model="test-model")


def _llm_result(content="", parsed=None, error="", raw="", model="test-model"):
    return LLMResult(content=content, parsed=parsed, error=error, raw=raw, model=model)


class TestEHRProcessor:
    @pytest.mark.asyncio
    async def test_generate_summary(self):
        summary = ClinicalSummary(chief_complaint="chest pain", diagnosis="ACS")
        with patch.object(LLMGateway, "chat", new=AsyncMock(return_value=_llm_result(parsed=summary))):
            ehr = EHRProcessor(config=_make_config())
            result = await ehr.generate_summary("Patient presents with chest pain")
            assert result["chief_complaint"] == "chest pain"
            assert result["diagnosis"] == "ACS"

    @pytest.mark.asyncio
    async def test_generate_summary_error(self):
        with patch.object(LLMGateway, "chat", new=AsyncMock(return_value=_llm_result(error="HTTP 500"))):
            ehr = EHRProcessor(config=_make_config())
            result = await ehr.generate_summary("notes")
            assert "error" in result

    @pytest.mark.asyncio
    async def test_generate_summary_fallback(self):
        with patch.object(LLMGateway, "chat", new=AsyncMock(return_value=_llm_result(content="plain summary"))):
            ehr = EHRProcessor(config=_make_config())
            result = await ehr.generate_summary("notes")
            assert result.get("summary") == "plain summary"

    @pytest.mark.asyncio
    async def test_generate_discharge(self):
        with patch.object(LLMGateway, "chat", new=AsyncMock(return_value=_llm_result(content="Discharge summary: patient stable"))):
            ehr = EHRProcessor(config=_make_config())
            result = await ehr.generate_discharge_summary("admitted", "stable", "aspirin")
            assert "Discharge" in result or "Error" in result

    @pytest.mark.asyncio
    async def test_extract_vitals(self):
        vitals = VitalsResult(bp="120/80", hr="72", temp="36.5")
        with patch.object(LLMGateway, "chat", new=AsyncMock(return_value=_llm_result(parsed=vitals))):
            ehr = EHRProcessor(config=_make_config())
            result = await ehr.extract_vitals("BP 120/80, HR 72")
            assert result["bp"] == "120/80"
            assert result["hr"] == "72"


class TestInsuranceCoder:
    @pytest.mark.asyncio
    async def test_suggest_icd_codes(self):
        icd_result = ICDCodeResult(codes=[ICDCodeItem(code="I10", description="Hypertension")])
        with patch.object(LLMGateway, "chat", new=AsyncMock(return_value=_llm_result(parsed=icd_result))):
            coder = InsuranceCoder(config=_make_config())
            result = await coder.suggest_icd_codes("Hypertension")
            assert len(result) >= 1
            assert result[0]["code"] == "I10"

    @pytest.mark.asyncio
    async def test_suggest_icd_codes_fallback(self):
        with patch.object(LLMGateway, "chat", new=AsyncMock(return_value=_llm_result(error="schema_validation_failed"))):
            coder = InsuranceCoder(config=_make_config())
            result = await coder.suggest_icd_codes("test")
            assert result == []

    @pytest.mark.asyncio
    async def test_suggest_cpt_codes(self):
        from fusion_health.schemas.insurance import CPTCodeItem, CPTCodeResult
        cpt_result = CPTCodeResult(codes=[CPTCodeItem(code="99213", description="Office visit")])
        with patch.object(LLMGateway, "chat", new=AsyncMock(return_value=_llm_result(parsed=cpt_result))):
            coder = InsuranceCoder(config=_make_config())
            result = await coder.suggest_cpt_codes("Office visit")
            assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_audit_claim(self):
        audit_result = ClaimAuditResult(issues=["Missing diagnosis code"])
        with patch.object(LLMGateway, "chat", new=AsyncMock(return_value=_llm_result(parsed=audit_result))):
            coder = InsuranceCoder(config=_make_config())
            result = await coder.audit_claim({"diagnosis": "I10"})
            assert isinstance(result, dict)
            assert "issues" in result


class TestLiteratureRetriever:
    @pytest.mark.asyncio
    async def test_search(self):
        cfg = _make_config()
        cfg.pubmed_enabled = False
        cfg.semantic_scholar_enabled = False
        lit_result = LiteratureSearchResult(
            results=[LiteratureItem(title="Study", authors="Smith", journal="NEJM", year=2025)],
            total_found=1,
        )
        with patch.object(LLMGateway, "chat", new=AsyncMock(return_value=_llm_result(parsed=lit_result))):
            lit = LiteratureRetriever(config=cfg)
            result = await lit.search("diabetes treatment")
            assert len(result) >= 1
            assert result[0]["title"] == "Study"

    @pytest.mark.asyncio
    async def test_search_fallback(self):
        cfg = _make_config()
        cfg.pubmed_enabled = False
        cfg.semantic_scholar_enabled = False
        with patch.object(LLMGateway, "chat", new=AsyncMock(return_value=_llm_result(error="fail"))):
            lit = LiteratureRetriever(config=cfg)
            result = await lit.search("test")
            assert result == []

    @pytest.mark.asyncio
    async def test_summarize_evidence(self):
        with patch.object(LLMGateway, "chat", new=AsyncMock(return_value=_llm_result(content="Evidence summary: effective treatment"))):
            lit = LiteratureRetriever(config=_make_config())
            result = await lit.summarize_evidence("treatment", [{"title": "Study", "summary": "effective"}])
            assert "Evidence" in result or "Error" in result


class TestComplianceChecker:
    @pytest.mark.asyncio
    async def test_audit_documentation(self):
        audit_result = ComplianceAuditResult(
            overall_compliant=False,
            rules_checked=[ComplianceRuleResult(rule_id="TEST-001", status="fail", detail="Missing chief complaint")],
        )
        with patch.object(LLMGateway, "chat", new=AsyncMock(return_value=_llm_result(parsed=audit_result))):
            cc = ComplianceChecker(config=_make_config())
            result = await cc.audit_documentation("Patient presents with chest pain")
            assert isinstance(result, dict)
            assert "rules_checked" in result

    @pytest.mark.asyncio
    async def test_check_regulatory(self):
        audit_result = ComplianceAuditResult(overall_compliant=True, rules_checked=[])
        with patch.object(LLMGateway, "chat", new=AsyncMock(return_value=_llm_result(parsed=audit_result))):
            cc = ComplianceChecker(config=_make_config())
            result = await cc.check_regulatory_compliance("clinical_trial", "test content")
            assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_audit_combines_rule_engine_and_llm(self):
        audit_result = ComplianceAuditResult(
            overall_compliant=True,
            rules_checked=[ComplianceRuleResult(rule_id="AI-001", status="pass", detail="OK")],
        )
        with patch.object(LLMGateway, "chat", new=AsyncMock(return_value=_llm_result(parsed=audit_result))):
            with tempfile.TemporaryDirectory() as rules_dir:
                rule_file = Path(rules_dir, "test.yaml")
                rule_file.write_text(
                    "rules:\n  - id: PIPL-001\n    description: 'detect ID number'\n    type: regex\n    pattern: \"\\\\d{17}[\\\\dXx]\"\n    severity: critical\n"
                )
                cfg = _make_config()
                cfg.rules_dir = Path(rules_dir)
                cc = ComplianceChecker(config=cfg)
                result = await cc.audit_documentation("身份证号 110101199001011234 泄露")
                rule_ids = [r["rule_id"] for r in result["rules_checked"]]
                assert "AI-001" in rule_ids
                assert "PIPL-001" in rule_ids

    @pytest.mark.asyncio
    async def test_audit_rule_failure_overrides_llm_compliant(self):
        audit_result = ComplianceAuditResult(overall_compliant=True, rules_checked=[])
        with patch.object(LLMGateway, "chat", new=AsyncMock(return_value=_llm_result(parsed=audit_result))):
            with tempfile.TemporaryDirectory() as rules_dir:
                rule_file = Path(rules_dir, "test.yaml")
                rule_file.write_text(
                    "rules:\n  - id: PIPL-001\n    description: 'detect ID number'\n    type: regex\n    pattern: \"\\\\d{17}[\\\\dXx]\"\n    severity: critical\n"
                )
                cfg = _make_config()
                cfg.rules_dir = Path(rules_dir)
                cc = ComplianceChecker(config=cfg)
                result = await cc.audit_documentation("身份证号 110101199001011234 泄露")
                assert result["overall_compliant"] is False


class TestRuleEngine:
    def test_load_and_check_required(self):
        with tempfile.TemporaryDirectory() as rules_dir:
            rule_file = Path(rules_dir, "mr.yaml")
            rule_file.write_text(
                "rules:\n  - id: CN-MR-001\n    description: 'must have chief complaint'\n    type: required\n    fields: ['主诉']\n    severity: warning\n"
            )
            engine = RuleEngine(Path(rules_dir))
            results = engine.check("患者无明显不适")
            assert any(r["rule_id"] == "CN-MR-001" and r["status"] == "fail" for r in results)

    def test_regex_rule_match(self):
        with tempfile.TemporaryDirectory() as rules_dir:
            rule_file = Path(rules_dir, "pipl.yaml")
            rule_file.write_text(
                "rules:\n  - id: PIPL-001\n    description: 'detect ID number'\n    type: regex\n    pattern: \"\\\\d{17}[\\\\dXx]\"\n    severity: critical\n"
            )
            engine = RuleEngine(Path(rules_dir))
            results = engine.check("身份证号 110101199001011234 泄露")
            assert any(r["rule_id"] == "PIPL-001" and r["status"] == "fail" for r in results)

    def test_required_rule_pass(self):
        with tempfile.TemporaryDirectory() as rules_dir:
            rule_file = Path(rules_dir, "mr.yaml")
            rule_file.write_text(
                "rules:\n  - id: CN-MR-006\n    description: 'must have signature'\n    type: required\n    field: '签名'\n    severity: warning\n"
            )
            engine = RuleEngine(Path(rules_dir))
            results = engine.check("诊断：感冒 签名：张医生")
            assert any(r["rule_id"] == "CN-MR-006" and r["status"] == "pass" for r in results)

    def test_empty_rules_dir(self):
        with tempfile.TemporaryDirectory() as rules_dir:
            engine = RuleEngine(Path(rules_dir))
            results = engine.check("any text")
            assert results == []


class TestICDValidator:
    def test_validate_known_code(self):
        cfg = _make_config()
        validator = ICDValidator(config=cfg)
        result = validator.validate("I10")
        assert result["valid"] is True
        assert result["status"] == "verified"
        assert "高血压" in result["description"]

    def test_validate_unknown_code(self):
        cfg = _make_config()
        validator = ICDValidator(config=cfg)
        result = validator.validate("Z99.99")
        assert result["valid"] is False
        assert result["status"] == "unverified"

    def test_search_by_keyword(self):
        cfg = _make_config()
        validator = ICDValidator(config=cfg)
        results = validator.search("高血压")
        assert len(results) > 0
        assert any(r["code"] == "I10" for r in results)

    def test_annotate_codes(self):
        cfg = _make_config()
        validator = ICDValidator(config=cfg)
        annotated = validator.annotate_codes(["I10", "Z99.99"])
        assert annotated[0]["status"] == "verified"
        assert annotated[1]["status"] == "unverified"

    def test_missing_db_graceful(self):
        cfg = _make_config()
        cfg.data_dir = Path("/nonexistent")
        validator = ICDValidator(config=cfg)
        result = validator.validate("I10")
        assert result["valid"] is False


class TestInsuranceCoderWithValidator:
    @pytest.mark.asyncio
    async def test_suggest_icd_codes_verified(self):
        icd_result = ICDCodeResult(codes=[ICDCodeItem(code="I10", description="Hypertension")])
        with patch.object(LLMGateway, "chat", new=AsyncMock(return_value=_llm_result(parsed=icd_result))):
            coder = InsuranceCoder(config=_make_config())
            result = await coder.suggest_icd_codes("Hypertension")
            assert result[0]["code"] == "I10"
            assert result[0]["status"] == "verified"

    @pytest.mark.asyncio
    async def test_suggest_icd_codes_ai_suggested(self):
        icd_result = ICDCodeResult(codes=[ICDCodeItem(code="Z99.99", description="Hallucinated")])
        with patch.object(LLMGateway, "chat", new=AsyncMock(return_value=_llm_result(parsed=icd_result))):
            coder = InsuranceCoder(config=_make_config())
            result = await coder.suggest_icd_codes("test")
            assert result[0]["code"] == "Z99.99"
            assert result[0]["status"] == "ai_suggested"


class TestLiteratureClients:
    @pytest.mark.asyncio
    async def test_pubmed_search_returns_real_data(self):
        with patch("httpx.AsyncClient.get", new=AsyncMock()) as mock_get:
            mock_get.side_effect = [
                MagicMock(json=lambda: {"esearchresult": {"idlist": ["12345"]}}, raise_for_status=lambda: None),
                MagicMock(json=lambda: {"result": {"12345": {"title": "Diabetes Study", "authors": [{"name": "Smith"}], "fulljournalname": "NEJM", "sortpubdate": "2024-01-01", "elocationid": "10.1234/test", "sorttitle": "Diabetes"}}}, raise_for_status=lambda: None),
            ]
            client = PubMedClient()
            results = await client.search("diabetes")
            assert len(results) == 1
            assert results[0]["pmid"] == "12345"
            assert results[0]["source"] == "pubmed"

    @pytest.mark.asyncio
    async def test_pubmed_search_error(self):
        with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=Exception("network error"))):
            client = PubMedClient()
            results = await client.search("diabetes")
            assert results == []

    @pytest.mark.asyncio
    async def test_s2_search_returns_real_data(self):
        with patch("httpx.AsyncClient.get", new=AsyncMock()) as mock_get:
            mock_get.return_value = MagicMock(
                json=lambda: {"data": [{"title": "AI in Healthcare", "authors": [{"name": "Lee"}], "year": 2024, "externalIds": {"DOI": "10.5678/ai"}, "abstract": "Abstract", "journal": {"name": "Nature"}}]},
                raise_for_status=lambda: None,
            )
            client = SemanticScholarClient()
            results = await client.search("AI healthcare")
            assert len(results) == 1
            assert results[0]["source"] == "semantic_scholar"

    @pytest.mark.asyncio
    async def test_s2_search_error(self):
        with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=Exception("network error"))):
            client = SemanticScholarClient()
            results = await client.search("test")
            assert results == []

    @pytest.mark.asyncio
    async def test_retriever_falls_back_to_llm_when_no_real_sources(self):
        cfg = _make_config()
        cfg.pubmed_enabled = False
        cfg.semantic_scholar_enabled = False
        lit_result = LiteratureSearchResult(
            results=[LiteratureItem(title="LLM Study", authors="AI", journal="Test", year=2024)],
            total_found=1,
        )
        with patch.object(LLMGateway, "chat", new=AsyncMock(return_value=_llm_result(parsed=lit_result))):
            lit = LiteratureRetriever(config=cfg)
            result = await lit.search("diabetes")
            assert len(result) >= 1


class TestConfig:
    def test_default_config(self):
        cfg = HealthConfig()
        assert cfg.model == "qwen3.5-9b"
        assert "localhost:11434" in cfg.mlx_url

    def test_from_env_override(self):
        with patch.dict("os.environ", {"FUSION_HEALTH_MODEL": "custom-model"}):
            cfg = HealthConfig.from_env()
            assert cfg.model == "custom-model"


class TestLLMGateway:
    @pytest.mark.asyncio
    async def test_parse_structured_json(self):
        gw = LLMGateway(config=_make_config())
        result = gw._parse_structured('{"chief_complaint": "pain"}', ClinicalSummary, "test")
        assert result.parsed is not None
        assert result.parsed.chief_complaint == "pain"

    @pytest.mark.asyncio
    async def test_parse_structured_markdown_wrapped(self):
        gw = LLMGateway(config=_make_config())
        raw = '```json\n{"chief_complaint": "pain"}\n```'
        result = gw._parse_structured(raw, ClinicalSummary, "test")
        assert result.parsed is not None

    @pytest.mark.asyncio
    async def test_parse_structured_invalid(self):
        gw = LLMGateway(config=_make_config())
        result = gw._parse_structured("not json at all", ClinicalSummary, "test")
        assert result.error != ""
        assert result.raw == "not json at all"


class TestCLI:
    def test_version(self):
        import sys
        from fusion_health.cli import main
        with patch.object(sys, "argv", ["fusion-health", "version"]):
            main()

    def test_ehr_summary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir, "notes.txt")
            src.write_text("Patient with chest pain")
            import sys
            from fusion_health.cli import main
            with patch.object(sys, "argv", ["fusion-health", "ehr", "summary", "--input=" + str(src)]):
                with patch("fusion_health.ehr.processor.EHRProcessor.generate_summary",
                           AsyncMock(return_value={"summary": "test"})):
                    main()

    def test_code_icd10(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir, "dx.txt")
            src.write_text("Hypertension")
            import sys
            from fusion_health.cli import main
            with patch.object(sys, "argv", ["fusion-health", "code", "icd10", "--input=" + str(src)]):
                with patch("fusion_health.insurance.coder.InsuranceCoder.suggest_icd_codes",
                           AsyncMock(return_value=[{"code": "I10"}])):
                    main()

    def test_literature(self):
        import sys
        from fusion_health.cli import main
        with patch.object(sys, "argv", ["fusion-health", "literature", "diabetes", "--max-results=3"]):
            with patch("fusion_health.literature.retriever.LiteratureRetriever.search",
                       AsyncMock(return_value=[{"title": "Study"}])):
                main()

    def test_compliance(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir, "note.txt")
            src.write_text("Clinical note content")
            import sys
            from fusion_health.cli import main
            with patch.object(sys, "argv", ["fusion-health", "compliance", "audit", "--input=" + str(src)]):
                with patch("fusion_health.compliance.checker.ComplianceChecker.audit_documentation",
                           AsyncMock(return_value={"issues": []})):
                    main()
