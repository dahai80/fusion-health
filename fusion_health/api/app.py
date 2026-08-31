from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from importlib.metadata import version as pkg_version

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..config import HealthConfig
from .middleware import APIKeyMiddleware
from .routes import chat, compliance, ehr, health, insurance, literature, tcm

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = HealthConfig.from_env()
    app.state.config = config
    logger.info("Fusion-Health API started: model=%s", config.model)
    yield
    logger.info("Fusion-Health API shutdown")


def create_app(config: HealthConfig | None = None) -> FastAPI:
    try:
        ver = pkg_version("fusion-health")
    except Exception:
        ver = "0.0.0"
    app = FastAPI(
        title="Fusion-Health API",
        description="Local AI healthcare assistant",
        version=ver,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(APIKeyMiddleware)

    if config:
        app.state.config = config

    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(ehr.router, prefix="/api/v1/ehr", tags=["ehr"])
    app.include_router(insurance.router, prefix="/api/v1/insurance", tags=["insurance"])
    app.include_router(literature.router, prefix="/api/v1/literature", tags=["literature"])
    app.include_router(compliance.router, prefix="/api/v1/compliance", tags=["compliance"])
    app.include_router(tcm.router, prefix="/api/v1/tcm", tags=["tcm"])
    app.include_router(chat.router, prefix="/api/v1/chat", tags=["chat"])

    return app


app = create_app()
