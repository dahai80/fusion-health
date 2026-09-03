from __future__ import annotations

import hashlib
import hmac
import logging
import os
import sqlite3
import threading
import time
import uuid
from collections import defaultdict, deque
from pathlib import Path

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)

EXEMPT_PATHS = {"/api/v1/health", "/api/v1/health/ready", "/api/v1/metrics", "/docs", "/openapi.json", "/redoc"}


def _normalize_path(path: str) -> str:
    if not path:
        return "/"
    norm = path
    while "//" in norm:
        norm = norm.replace("//", "/")
    try:
        from urllib.parse import unquote
        norm = unquote(norm)
    except Exception as e:
        logger.debug("url decode skipped: %s", e)
    return norm.lower()


def _owner_id(api_key: str, client_host: str) -> str:
    if api_key:
        return hashlib.sha256(api_key.encode()).hexdigest()[:16]
    return f"local:{client_host}"


class RateLimiter:
    def __init__(self, rpm: int):
        self.rpm = rpm
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._db_path = os.getenv("FUSION_HEALTH_RATE_LIMIT_DB", "")
        self._db_lock = threading.Lock()
        if self._db_path and rpm > 0:
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
            try:
                conn = sqlite3.connect(self._db_path, timeout=2.0, isolation_level=None)
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS hits (owner TEXT, ts REAL, PRIMARY KEY (owner, ts))"
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_hits_ts ON hits (ts)")
                conn.close()
                logger.info("RateLimiter using shared SQLite backend: %s", self._db_path)
            except Exception as e:
                logger.warning("SQLite rate-limit backend init failed (%s), falling back to in-memory", e)
                self._db_path = ""
        if rpm > 0 and not self._db_path:
            workers = os.getenv("FUSION_HEALTH_WORKERS", "1")
            try:
                workers_n = int(workers)
            except ValueError:
                workers_n = 1
            if workers_n > 1:
                logger.warning(
                    "RateLimiter is per-process (in-memory); %d workers → effective limit %d rpm (N×%d). "
                    "Set FUSION_HEALTH_RATE_LIMIT_DB for cross-worker shared limiting.",
                    workers_n, rpm * workers_n, rpm,
                )

    def allow(self, owner_id: str) -> bool:
        if self.rpm <= 0:
            return True
        if self._db_path:
            return self._allow_shared(owner_id)
        return self._allow_local(owner_id)

    def _allow_local(self, owner_id: str) -> bool:
        now = time.monotonic()
        window = 60.0
        hits = self._hits[owner_id]
        cutoff = now - window
        while hits and hits[0] < cutoff:
            hits.popleft()
        if len(hits) >= self.rpm:
            return False
        hits.append(now)
        return True

    def _allow_shared(self, owner_id: str) -> bool:
        now = time.time()
        cutoff = now - 60.0
        try:
            with self._db_lock:
                conn = sqlite3.connect(self._db_path, timeout=2.0, isolation_level=None)
                try:
                    conn.execute("BEGIN IMMEDIATE")
                    conn.execute("DELETE FROM hits WHERE ts < ?", (cutoff,))
                    row = conn.execute(
                        "SELECT COUNT(*) FROM hits WHERE owner = ?", (owner_id,)
                    ).fetchone()
                    count = row[0] if row else 0
                    if count >= self.rpm:
                        conn.execute("ROLLBACK")
                        return False
                    conn.execute(
                        "INSERT OR IGNORE INTO hits (owner, ts) VALUES (?, ?)", (owner_id, now)
                    )
                    conn.execute("COMMIT")
                    return True
                finally:
                    conn.close()
        except Exception as e:
            logger.warning("SQLite rate-limit check failed (%s), allowing request", e)
            return True


class APIKeyMiddleware(BaseHTTPMiddleware):
    _instance = None

    def __init__(self, app):
        super().__init__(app)
        try:
            rpm = int(os.getenv("FUSION_HEALTH_RATE_LIMIT_RPM", "60") or "60")
        except ValueError:
            rpm = 60
        self.limiter = RateLimiter(rpm)
        self._requests = 0
        self._auth_failures = 0
        self._rate_rejections = 0
        APIKeyMiddleware._instance = self

    def metrics_snapshot(self) -> dict:
        tracked = self._tracked_owners()
        return {
            "rpm_limit": self.limiter.rpm,
            "rate_limit_backend": "sqlite" if self.limiter._db_path else "memory",
            "tracked_owners": tracked,
            "total_requests": self._requests,
            "auth_failures": self._auth_failures,
            "rate_rejections": self._rate_rejections,
        }

    def _tracked_owners(self) -> int:
        if self.limiter._db_path:
            cutoff = time.time() - 60.0
            try:
                conn = sqlite3.connect(self.limiter._db_path, timeout=2.0)
                try:
                    row = conn.execute(
                        "SELECT COUNT(DISTINCT owner) FROM hits WHERE ts > ?", (cutoff,)
                    ).fetchone()
                    return row[0] if row else 0
                finally:
                    conn.close()
            except Exception as e:
                logger.warning("tracked_owners DB read failed (%s)", e)
                return 0
        return len(self.limiter._hits)

    async def dispatch(self, request: Request, call_next):
        request.state.request_id = str(uuid.uuid4())
        path = _normalize_path(request.url.path)

        if request.method == "OPTIONS":
            return await self._disclaimer(call_next, request)

        if path in EXEMPT_PATHS or not path.startswith("/api/"):
            return await self._disclaimer(call_next, request)

        self._requests += 1
        api_key = os.getenv("FUSION_HEALTH_API_KEY", "")
        if not api_key:
            client_host = request.client.host if request.client else ""
            if client_host in ("127.0.0.1", "::1", "localhost"):
                owner = _owner_id("", client_host)
                request.state.owner_id = owner
                return await self._gate(request, call_next, owner, path)
            logger.warning(
                "API key not set; rejecting non-localhost access: %s %s",
                request.method, path,
            )
            self._auth_failures += 1
            return JSONResponse(
                status_code=401,
                content={"detail": "API key required: set FUSION_HEALTH_API_KEY for remote access"},
            )

        key = request.headers.get("X-API-Key", "")
        if not hmac.compare_digest(key, api_key):
            logger.warning("Unauthorized API access: %s %s", request.method, path)
            self._auth_failures += 1
            return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})

        owner = _owner_id(api_key, request.client.host if request.client else "")
        request.state.owner_id = owner
        return await self._gate(request, call_next, owner, path)

    async def _gate(self, request, call_next, owner, path):
        if not self.limiter.allow(owner):
            logger.warning("Rate limit exceeded: owner=%s %s %s", owner, request.method, path)
            self._rate_rejections += 1
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded", "retry_after": 60},
            )
        return await self._disclaimer(call_next, request)

    @staticmethod
    async def _disclaimer(call_next, request):
        response = await call_next(request)
        response.headers["X-Fusion-Disclaimer"] = (
            "advisory-only; not a diagnosis; physician must make final decision; not NMPA-registered"
        )
        return response
