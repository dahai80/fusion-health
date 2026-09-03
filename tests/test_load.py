from __future__ import annotations

import asyncio

import httpx
import pytest


def _slo_ms() -> float:
    import os
    return float(os.getenv("FUSION_HEALTH_LOAD_SLO_MS", "2000"))


@pytest.mark.asyncio
async def test_health_endpoint_meets_slo():
    from fusion_health.api.app import create_app
    from fusion_health.config import HealthConfig

    cfg = HealthConfig()
    cfg.pubmed_enabled = False
    cfg.semantic_scholar_enabled = False
    app = create_app(cfg)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", headers={"X-API-Key": "x"}, timeout=30.0) as client:
        # warmup
        await client.get("/api/v1/health")

        concurrency = 10
        per = 20

        async def hit():
            r = await client.get("/api/v1/health")
            return r.elapsed.total_seconds()

        async def worker(results):
            for _ in range(per):
                results.append(await hit())

        results: list[float] = []
        await asyncio.gather(*[worker(results) for _ in range(concurrency)])

    results.sort()
    n = len(results)
    assert n == concurrency * per
    p95 = results[int(n * 0.95)]
    assert p95 * 1000 <= _slo_ms(), f"p95={p95*1000:.0f}ms exceeds SLO {_slo_ms():.0f}ms"


@pytest.mark.asyncio
async def test_readiness_endpoint_under_concurrency():
    from fusion_health.api.app import create_app
    from fusion_health.config import HealthConfig

    cfg = HealthConfig()
    cfg.pubmed_enabled = False
    cfg.semantic_scholar_enabled = False
    app = create_app(cfg)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", headers={"X-API-Key": "x"}, timeout=30.0) as client:
        concurrency = 15

        async def hit():
            r = await client.get("/api/v1/health/ready")
            return r.status_code, r.elapsed.total_seconds()

        async def worker(results):
            for _ in range(10):
                results.append(await hit())

        results: list[float] = []
        await asyncio.gather(*[worker(results) for _ in range(concurrency)])

    statuses = {s for s, _ in results}
    assert statuses <= {200, 503}, f"unexpected status codes: {statuses}"
    times = sorted(t for _, t in results)
    p95 = times[int(len(times) * 0.95)]
    assert p95 * 1000 <= _slo_ms(), f"ready p95={p95*1000:.0f}ms exceeds SLO"
