from .ehr.processor import EHRProcessor
from .ehr.fhir_mapper import FHIRMapper
from .insurance.coder import InsuranceCoder
from .insurance.icd_validator import ICDValidator
from .insurance.cn_coding import CNMedicalCoder, DRGHelper, InsuranceCatalogMatcher, ICD9CM3Validator
from .literature.retriever import LiteratureRetriever
from .literature.pubmed_client import PubMedClient
from .literature.semantic_scholar import SemanticScholarClient
from .compliance.checker import ComplianceChecker
from .compliance.rule_engine import RuleEngine
from .tcm.assistant import TCMAssistant
from .artifact_client import ArtifactClient
from .conversation import ConversationSession, ConversationMemory
from .templates import TemplateEngine
from .batch import BatchProcessor
from .config import HealthConfig

__all__ = [
    "EHRProcessor", "FHIRMapper",
    "InsuranceCoder", "ICDValidator", "CNMedicalCoder", "DRGHelper",
    "InsuranceCatalogMatcher", "ICD9CM3Validator",
    "LiteratureRetriever", "PubMedClient", "SemanticScholarClient",
    "ComplianceChecker", "RuleEngine",
    "TCMAssistant", "ArtifactClient", "HealthConfig",
    "create_app", "ConversationSession", "ConversationMemory",
    "TemplateEngine", "BatchProcessor",
]


def __getattr__(name: str):
    if name == "create_app":
        from .api.app import create_app
        return create_app
    raise AttributeError(f"module 'fusion_health' has no attribute {name!r}")
