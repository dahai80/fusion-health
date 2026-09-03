from __future__ import annotations

import logging

from ..config import HealthConfig
from ..llm_gateway import LLMGateway

logger = logging.getLogger(__name__)

_shared_gateway: LLMGateway | None = None


def get_gateway(config: HealthConfig | None = None) -> LLMGateway:
    global _shared_gateway
    if _shared_gateway is None:
        cfg = config or HealthConfig.from_env()
        _shared_gateway = LLMGateway(cfg)
        logger.info("Shared LLMGateway initialized (pooled httpx client)")
    return _shared_gateway


async def close_gateway() -> None:
    global _shared_gateway
    if _shared_gateway is not None:
        await _shared_gateway.close()
        _shared_gateway = None
        logger.info("Shared LLMGateway closed")
