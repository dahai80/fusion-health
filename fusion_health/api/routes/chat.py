from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse

from ...audit import log_access
from ...conversation import ConversationSession
from ..gateway_provider import get_gateway
from ..sse import sse_response

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_SESSIONS = 1000
SESSION_TTL = 1800.0
_sessions: dict[tuple[str, str], ConversationSession] = {}
_session_times: dict[tuple[str, str], float] = {}
_reaper_task: asyncio.Task | None = None

DEFAULT_OWNER = "anonymous"
SESSION_ID_RE = __import__("re").compile(r"^[a-zA-Z0-9_-]{1,64}$")


async def _reaper():
    while True:
        await asyncio.sleep(300)
        now = time.time()
        stale = [k for k, t in _session_times.items() if now - t > SESSION_TTL]
        for key in stale:
            session = _sessions.pop(key, None)
            _session_times.pop(key, None)
            if session is not None:
                try:
                    session.save()
                except Exception as e:
                    logger.warning("Error saving stale session %s: %s", key[1], e)
                try:
                    await session.close()
                except Exception as e:
                    logger.warning("Error closing stale session %s: %s", key[1], e)
            logger.info("Reaped stale chat session: %s/%s", key[0], key[1])


def start_reaper() -> None:
    global _reaper_task
    if _reaper_task is None or _reaper_task.done():
        _reaper_task = asyncio.create_task(_reaper())


async def close_all_sessions():
    for key in list(_sessions.keys()):
        session = _sessions.pop(key, None)
        _session_times.pop(key, None)
        if session is not None:
            try:
                session.save()
            except Exception as e:
                logger.warning("Error saving session %s on shutdown: %s", key[1], e)
            try:
                await session.close()
            except Exception as e:
                logger.warning("Error closing session %s on shutdown: %s", key[1], e)
    logger.info("Closed all chat sessions on shutdown")


def _owner(request: Request) -> str:
    return getattr(request.state, "owner_id", DEFAULT_OWNER)


async def _evict_if_over(owner: str):
    owner_sessions = {k: v for k, v in _session_times.items() if k[0] == owner}
    while len(owner_sessions) > MAX_SESSIONS:
        oldest_key = min(owner_sessions, key=owner_sessions.get)
        evicted = _sessions.pop(oldest_key, None)
        _session_times.pop(oldest_key, None)
        del owner_sessions[oldest_key]
        if evicted is not None:
            try:
                await evicted.close()
            except Exception as e:
                logger.warning("Error closing evicted session %s: %s", oldest_key[1], e)
        logger.info("Evicted oldest chat session: %s/%s", oldest_key[0], oldest_key[1])


class ChatStartRequest(BaseModel):
    session_id: str | None = Field(default=None, pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    system_prompt: str | None = None


class ChatMessageRequest(BaseModel):
    session_id: str = Field(..., pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    message: str = Field(..., min_length=1, max_length=5000)


class ChatSaveRequest(BaseModel):
    session_id: str = Field(..., pattern=r"^[a-zA-Z0-9_-]{1,64}$")


def _not_found(session_id: str) -> JSONResponse:
    return JSONResponse(
        {"error": "session_not_found", "session_id": session_id},
        status_code=404,
    )


@router.post("/start")
async def start_session(request: Request, body: ChatStartRequest) -> dict[str, Any]:
    owner = _owner(request)
    config = request.app.state.config
    session = ConversationSession(config)
    sid = session.start(session_id=body.session_id, system_prompt=body.system_prompt)
    key = (owner, sid)
    _sessions[key] = session
    _session_times[key] = time.time()
    await _evict_if_over(owner)
    log_access(owner, "POST", "/api/v1/chat/start", "chat_start", "ok", request_id=getattr(request.state, "request_id", ""))
    return {"session_id": sid, "status": "started"}


@router.post("/message")
async def send_message(request: Request, body: ChatMessageRequest) -> dict[str, Any]:
    owner = _owner(request)
    key = (owner, body.session_id)
    session = _sessions.get(key)
    if not session:
        return _not_found(body.session_id)
    _session_times[key] = time.time()
    result = await session.chat(body.message)
    return {
        "session_id": body.session_id,
        "response": result.content,
        "error": result.error,
        "turn_count": session.memory.turn_count,
    }


@router.post("/message/stream")
async def send_message_stream(request: Request, body: ChatMessageRequest):
    owner = _owner(request)
    key = (owner, body.session_id)
    session = _sessions.get(key)
    if not session:
        return _not_found(body.session_id)
    _session_times[key] = time.time()
    session.memory.add_user_message(body.message)
    config = request.app.state.config
    gateway = get_gateway(config)
    tokens = gateway.chat_stream(messages=session.memory.get_messages())

    async def _on_done(full_content: str):
        session.memory.add_assistant_message(full_content)

    return sse_response(tokens, request, gateway, on_done=_on_done)


@router.post("/save")
async def save_session(request: Request, body: ChatSaveRequest) -> dict[str, Any]:
    owner = _owner(request)
    key = (owner, body.session_id)
    session = _sessions.get(key)
    if not session:
        return _not_found(body.session_id)
    session.save()
    return {"session_id": body.session_id, "status": "saved"}


@router.get("/sessions")
async def list_sessions(request: Request) -> dict[str, Any]:
    owner = _owner(request)
    return {
        "sessions": [
            {"session_id": key[1], "turn_count": s.memory.turn_count}
            for key, s in _sessions.items()
            if key[0] == owner
        ]
    }


@router.delete("/sessions/{session_id}")
async def delete_session(request: Request, session_id: str) -> dict[str, Any]:
    owner = _owner(request)
    key = (owner, session_id)
    session = _sessions.pop(key, None)
    _session_times.pop(key, None)
    if session:
        try:
            await session.close()
        except Exception as e:
            logger.warning("Error closing session %s: %s", session_id, e)
        return {"session_id": session_id, "status": "deleted"}
    return _not_found(session_id)
