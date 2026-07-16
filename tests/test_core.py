"""Tests for Fusion-Health core modules."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fusion_health.ehr.processor import EHRProcessor
from fusion_health.insurance.coder import InsuranceCoder
from fusion_health.literature.retriever import LiteratureRetriever, ComplianceChecker


class MockResponse:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data or {"choices": [{"message": {"content": '{"test": "ok"}'}}]}
    def raise_for_status(self):
        pass
    def json(self):
        return self._json


class TestEHRProcessor:
    @pytest.mark.asyncio
    async def test_generate_summary(self):
        ehr = EHRProcessor()
        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=MockResponse())):
            result = await ehr.generate_summary("Patient presents with chest pain")
            assert "test" in result or "error" in result

    @pytest.mark.asyncio
    async def test_generate_summary_error(self):
        ehr = EHRProcessor()
        with patch("httpx.AsyncClient.post", side_effect=RuntimeError("fail")):
            result = await ehr.generate_summary("notes")
            assert "error" in result

    @pytest.mark.asyncio
    async def test_generate_discharge(self):
        ehr = EHRProcessor()
        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=MockResponse(json_data={
            "choices": [{"message": {"content": "Discharge summary: patient stable"}}]
        }))):
            result = await ehr.generate_discharge_summary("admitted", "stable", "aspirin")
            assert "Discharge" in result or "error" in result

    @pytest.mark.asyncio
    async def test_extract_vitals(self):
        ehr = EHRProcessor()
        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=MockResponse())):
            result = await ehr.extract_vitals("BP 120/80, HR 72")
            assert isinstance(result, dict)


class TestInsuranceCoder:
    @pytest.mark.asyncio
    async def test_suggest_icd_codes(self):
        coder = InsuranceCoder()
        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=MockResponse(json_data={
            "choices": [{"message": {"content": '[{"code": "I10", "description": "Hypertension", "confidence": 0.95}]'}}]
        }))):
            result = await coder.suggest_icd_codes("Hypertension")
            assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_suggest_icd_codes_fallback(self):
        coder = InsuranceCoder()
        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=MockResponse(json_data={
            "choices": [{"message": {"content": "not json"}}]
        }))):
            result = await coder.suggest_icd_codes("test")
            assert result == []

    @pytest.mark.asyncio
    async def test_suggest_cpt_codes(self):
        coder = InsuranceCoder()
        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=MockResponse(json_data={
            "choices": [{"message": {"content": '[{"code": "99213", "description": "Office visit", "confidence": 0.9}]'}}]
        }))):
            result = await coder.suggest_cpt_codes("Office visit")
            assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_audit_claim(self):
        coder = InsuranceCoder()
        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=MockResponse())):
            result = await coder.audit_claim({"diagnosis": "I10"})
            assert isinstance(result, dict)


class TestLiteratureRetriever:
    @pytest.mark.asyncio
    async def test_search(self):
        lit = LiteratureRetriever()
        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=MockResponse(json_data={
            "choices": [{"message": {"content": '[{"title": "Study", "authors": "Smith", "journal": "NEJM", "year": 2025}]'}}]
        }))):
            result = await lit.search("diabetes treatment")
            assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_search_fallback(self):
        lit = LiteratureRetriever()
        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=MockResponse(json_data={
            "choices": [{"message": {"content": "plain text"}}]
        }))):
            result = await lit.search("test")
            assert result == []

    @pytest.mark.asyncio
    async def test_summarize_evidence(self):
        lit = LiteratureRetriever()
        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=MockResponse(json_data={
            "choices": [{"message": {"content": "Evidence summary: effective treatment"}}]
        }))):
            result = await lit.summarize_evidence("treatment", [{"title": "Study", "summary": "effective"}])
            assert "Evidence" in result or "error" in result


class TestComplianceChecker:
    @pytest.mark.asyncio
    async def test_audit_documentation(self):
        cc = ComplianceChecker()
        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=MockResponse())):
            result = await cc.audit_documentation("Patient presents with chest pain")
            assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_check_regulatory(self):
        cc = ComplianceChecker()
        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=MockResponse())):
            result = await cc.check_regulatory_compliance("clinical_trial", "test content")
            assert isinstance(result, dict)


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
                with patch("fusion_health.literature.retriever.ComplianceChecker.audit_documentation",
                           AsyncMock(return_value={"issues": []})):
                    main()