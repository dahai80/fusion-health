from __future__ import annotations

from pydantic import BaseModel

SOURCE_AI_UNVERIFIED = "ai_generated_unverified"


class TCMAnalysisResult(BaseModel):
    syndrome: str = ""
    formula: str = ""
    herbs: list[str] = []
    reasoning: str = ""
