from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from .config import HealthConfig
from .llm_gateway import LLMGateway
from .schemas.base import LLMResult

logger = logging.getLogger(__name__)


class ConversationMemory:
    def __init__(self, config: HealthConfig | None = None):
        self.config = config or HealthConfig.from_env()
        self._short_term: list[dict[str, str]] = []
        self._long_term: list[dict[str, str]] = []
        self._max_short_term = 20
        self._session_id: str = ""

    def start_session(self, session_id: str | None = None) -> str:
        if session_id is None:
            session_id = f"sess-{int(time.time())}"
        self._session_id = session_id
        self._short_term = []
        logger.info("Conversation session started: %s", session_id)
        return session_id

    def add_user_message(self, content: str):
        self._short_term.append({"role": "user", "content": content})
        self._trim_short_term()

    def add_assistant_message(self, content: str):
        self._short_term.append({"role": "assistant", "content": content})
        self._trim_short_term()

    def add_system_message(self, content: str):
        self._short_term.insert(0, {"role": "system", "content": content})

    def get_messages(self, include_long_term: bool = True) -> list[dict[str, str]]:
        messages = []
        if include_long_term and self._long_term:
            messages.extend(self._long_term)
        messages.extend(self._short_term)
        return messages

    def _trim_short_term(self):
        while len(self._short_term) > self._max_short_term:
            for i in range(len(self._short_term)):
                if self._short_term[i].get("role") != "system":
                    removed = self._short_term.pop(i)
                    if removed.get("role") in ("user", "assistant"):
                        self._long_term.append(removed)
                    break
            else:
                break
        if len(self._long_term) > 100:
            self._long_term = self._long_term[-50:]

    def clear_short_term(self):
        self._short_term = []

    def save(self, path: Path | None = None):
        if path is None:
            path = self.config.literature_cache_dir.parent / "conversations" / f"{self._session_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "session_id": self._session_id,
            "short_term": self._short_term,
            "long_term": self._long_term,
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Conversation saved: %s", path)

    def load(self, path: Path) -> str:
        data = json.loads(path.read_text(encoding="utf-8"))
        self._session_id = data.get("session_id", "")
        self._short_term = data.get("short_term", [])
        self._long_term = data.get("long_term", [])
        logger.info("Conversation loaded: %s, msgs=%d", self._session_id, len(self._short_term))
        return self._session_id

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def turn_count(self) -> int:
        return sum(1 for m in self._short_term if m.get("role") == "user")


class ConversationSession:
    def __init__(self, config: HealthConfig | None = None):
        self.config = config or HealthConfig.from_env()
        self._gateway = LLMGateway(self.config)
        self._memory = ConversationMemory(self.config)
        self._system_prompt = (
            "你是 Fusion-Health 医疗辅助AI。请基于患者信息提供专业医疗建议。"
            "所有建议仅供参考，不构成诊断。遇到不确定的情况请建议就医。"
        )

    def start(self, session_id: str | None = None, system_prompt: str | None = None) -> str:
        sid = self._memory.start_session(session_id)
        if system_prompt:
            self._system_prompt = system_prompt
        self._memory.add_system_message(self._system_prompt)
        return sid

    async def chat(self, user_input: str, **kwargs) -> LLMResult:
        self._memory.add_user_message(user_input)
        messages = self._memory.get_messages()
        result = await self._gateway.chat(messages=messages, **kwargs)
        if result.content:
            self._memory.add_assistant_message(result.content)
        else:
            self._memory.add_assistant_message(f"[错误: {result.error}]")
        return result

    @property
    def memory(self) -> ConversationMemory:
        return self._memory

    def save(self, path: Path | None = None):
        self._memory.save(path)

    def load(self, path: Path) -> str:
        return self._memory.load(path)

    async def close(self):
        await self._gateway.close()
