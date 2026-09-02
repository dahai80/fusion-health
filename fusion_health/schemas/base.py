from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel


class VerificationStatus(str, Enum):
    verified = "verified"
    ai_suggested = "ai_suggested"
    unverified = "unverified"
    invalid = "invalid"


class LLMResult(BaseModel):
    content: str = ""
    parsed: Any = None
    error: str = ""
    raw: str = ""
    model: str = ""

    @property
    def ok(self) -> bool:
        return self.error == ""
