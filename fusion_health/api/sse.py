from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator

from starlette.responses import StreamingResponse

logger = logging.getLogger(__name__)


async def _sse_generator(tokens: AsyncGenerator[str, None]) -> AsyncGenerator[str, None]:
    full = []
    try:
        async for token in tokens:
            full.append(token)
            yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'done': True, 'content': ''.join(full)}, ensure_ascii=False)}\n\n"
    except Exception as e:
        logger.error("SSE generator error: %s", e)
        yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"


def sse_response(tokens: AsyncGenerator[str, None]) -> StreamingResponse:
    return StreamingResponse(
        _sse_generator(tokens),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
