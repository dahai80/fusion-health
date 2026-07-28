from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from ...conversation import ConversationSession
from ...llm_gateway import LLMGateway
from ..sse import sse_response

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_SESSIONS = 1000
_sessions: dict[str, ConversationSession] = {}
_session_times: dict[str, float] = {}


def _evict_oldest():
    if len(_sessions) < MAX_SESSIONS:
        return
    oldest_sid = min(_session_times, key=_session_times.get)
    _sessions.pop(oldest_sid, None)
    _session_times.pop(oldest_sid, None)
    logger.info("Evicted oldest chat session: %s", oldest_sid)


class ChatStartRequest(BaseModel):
    session_id: str | None = None
    system_prompt: str | None = None


class ChatMessageRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1, max_length=5000)


class ChatSaveRequest(BaseModel):
    session_id: str = Field(..., min_length=1)


@router.post("/start")
async def start_session(request: Request, body: ChatStartRequest) -> dict[str, Any]:
    _evict_oldest()
    config = request.app.state.config
    session = ConversationSession(config)
    sid = session.start(session_id=body.session_id, system_prompt=body.system_prompt)
    _sessions[sid] = session
    _session_times[sid] = time.time()
    return {"session_id": sid, "status": "started"}


@router.post("/message")
async def send_message(request: Request, body: ChatMessageRequest) -> dict[str, Any]:
    session = _sessions.get(body.session_id)
    if not session:
        return {"error": "session_not_found", "session_id": body.session_id}
    _session_times[body.session_id] = time.time()
    result = await session.chat(body.message)
    return {
        "session_id": body.session_id,
        "response": result.content,
        "error": result.error,
        "turn_count": session.memory.turn_count,
    }


@router.post("/message/stream")
async def send_message_stream(request: Request, body: ChatMessageRequest):
    session = _sessions.get(body.session_id)
    if not session:
        from starlette.responses import JSONResponse
        return JSONResponse({"error": "session_not_found", "session_id": body.session_id}, status_code=404)
    _session_times[body.session_id] = time.time()
    session.memory.add_user_message(body.message)
    config = request.app.state.config
    gateway = LLMGateway(config)
    tokens = gateway.chat_stream(messages=session.memory.get_messages())
    return sse_response(tokens)


@router.post("/save")
async def save_session(request: Request, body: ChatSaveRequest) -> dict[str, Any]:
    session = _sessions.get(body.session_id)
    if not session:
        return {"error": "session_not_found", "session_id": body.session_id}
    session.save()
    return {"session_id": body.session_id, "status": "saved"}


@router.get("/sessions")
async def list_sessions() -> dict[str, Any]:
    return {
        "sessions": [
            {"session_id": sid, "turn_count": s.memory.turn_count}
            for sid, s in _sessions.items()
        ]
    }


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str) -> dict[str, Any]:
    session = _sessions.pop(session_id, None)
    _session_times.pop(session_id, None)
    if session:
        try:
            await session.close()
        except Exception as e:
            logger.warning("Error closing session %s: %s", session_id, e)
        return {"session_id": session_id, "status": "deleted"}
    return {"error": "session_not_found", "session_id": session_id}
