from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator

from starlette.requests import Request
from starlette.responses import StreamingResponse

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL = 15.0


async def _sse_generator(
    tokens: AsyncGenerator[str, None],
    request: Request,
    gateway=None,
    on_done=None,
) -> AsyncGenerator[str, None]:
    full: list[str] = []
    token_q: asyncio.Queue[str | None] = asyncio.Queue()
    consume_error: list[BaseException] = []

    async def _consume():
        try:
            async for token in tokens:
                await token_q.put(token)
        except BaseException as e:
            consume_error.append(e)
        finally:
            await token_q.put(None)

    consumer = asyncio.create_task(_consume())
    try:
        while True:
            try:
                item = await asyncio.wait_for(token_q.get(), timeout=HEARTBEAT_INTERVAL)
            except asyncio.TimeoutError:
                if await request.is_disconnected():
                    logger.info("SSE client disconnected (heartbeat), aborting stream")
                    break
                yield ": heartbeat\n\n"
                continue
            if item is None:
                break
            full.append(item)
            yield f"data: {json.dumps({'token': item}, ensure_ascii=False)}\n\n"
        if consume_error:
            e = consume_error[0]
            logger.error("SSE stream error: %s", e)
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
        else:
            yield f"data: {json.dumps({'done': True, 'content': ''.join(full)}, ensure_ascii=False)}\n\n"
            if on_done is not None:
                try:
                    await on_done("".join(full))
                except Exception as e:
                    logger.warning("SSE on_done callback failed: %s", e)
    except asyncio.CancelledError:
        logger.info("SSE generator cancelled by client disconnect")
        raise
    finally:
        if not consumer.done():
            consumer.cancel()
            try:
                await consumer
            except (asyncio.CancelledError, BaseException):
                pass
        if gateway is not None:
            try:
                await gateway.close()
            except Exception as e:
                logger.warning("SSE gateway close failed: %s", e)


def sse_response(
    tokens: AsyncGenerator[str, None],
    request: Request | None = None,
    gateway=None,
    on_done=None,
) -> StreamingResponse:
    if request is None:
        raise ValueError("sse_response requires a Request for disconnect detection")
    return StreamingResponse(
        _sse_generator(tokens, request, gateway, on_done),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
