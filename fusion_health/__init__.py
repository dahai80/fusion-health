"""Fusion-Health — Local AI healthcare assistant powered by fusion-mlx.

All model inference goes through fusion-mlx HTTP API.
Never imports cloud AI services directly. HIPAA-compliant by design (local-only).
"""

from .ehr.processor import EHRProcessor
from .insurance.coder import InsuranceCoder
from .literature.retriever import LiteratureRetriever
from .literature.retriever import ComplianceChecker

__all__ = ["EHRProcessor", "InsuranceCoder", "LiteratureRetriever", "ComplianceChecker"]