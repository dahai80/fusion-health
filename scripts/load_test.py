from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger("load_test")

# In-process ASGI transport — no network/port, deterministic, CI-safe.
# Real backend path: set FUSION_HEALTH_REAL_MODEL=1 + FUSION_HEALTH_LOAD_URL.


def _make_client(use_real: bool, base_url: str, api_key: str):
    if use_real:
        import httpx
        return httpx.AsyncClient(base_url=base_url, headers={"X-API-Key": api_key}, timeout=60.0), None
    import httpx
    from fusion_health.api.app import create_app
    from fusion_health.config import HealthConfig
    cfg = HealthConfig()
    cfg.pubmed_enabled = False
    cfg.semantic_scholar_enabled = False
    app = create_app(cfg)
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test", headers={"X-API-Key": "x"}, timeout=60.0)
    return client, app


async def _hit(client, path: str) -> float:
    t0 = time.perf_counter()
    try:
        r = await client.get(path)
        r.raise_for_status()
    except Exception:
        pass
    return time.perf_counter() - t0


async def _worker(client, path: str, n: int, results: list[float]):
    for _ in range(n):
        results.append(await _hit(client, path))


async def run(concurrency: int, total: int, path: str, use_real: bool, base_url: str, api_key: str):
    client, app = _make_client(use_real, base_url, api_key)
    # warmup 1 call (triggers lifespan, config load) so first hit isn't cold-start noise
    try:
        await _hit(client, path)
    except Exception:
        pass
    per = total // concurrency
    results: list[float] = []
    t0 = time.perf_counter()
    try:
        await asyncio.gather(*[_worker(client, path, per, results) for _ in range(concurrency)])
    finally:
        await client.aclose()
    elapsed = time.perf_counter() - t0
    if not results:
        logger.error("no results collected")
        return 1
    results.sort()
    n = len(results)
    rps = n / elapsed
    p50 = results[int(n * 0.50)]
    p95 = results[int(n * 0.95)]
    p99 = results[int(n * 0.99)] if n >= 100 else results[-1]
    print(f"concurrency={concurrency} total={n} elapsed={elapsed:.2f}s")
    print(f"throughput={rps:.1f} req/s")
    print(f"latency_ms: p50={p50*1000:.1f} p95={p95*1000:.1f} p99={p99*1000:.1f} max={results[-1]*1000:.1f}")
    # SLO gate: p95 < 2000ms for health/readiness (cheap endpoints)
    slo_ms = float(os.getenv("FUSION_HEALTH_LOAD_SLO_MS", "2000"))
    ok = p95 * 1000 <= slo_ms
    print(f"SLO p95<={slo_ms:.0f}ms: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 2


def main():
    p = argparse.ArgumentParser(description="Fusion-Health API load/perf test")
    p.add_argument("--concurrency", type=int, default=20)
    p.add_argument("--total", type=int, default=400)
    p.add_argument("--path", default="/api/v1/health")
    p.add_argument("--real", action="store_true", help="hit live server (FUSION_HEALTH_LOAD_URL)")
    args = p.parse_args()
    use_real = args.real or os.getenv("FUSION_HEALTH_REAL_MODEL") == "1"
    base_url = os.getenv("FUSION_HEALTH_LOAD_URL", "http://127.0.0.1:11469")
    api_key = os.getenv("FUSION_HEALTH_API_KEY", "")
    sys.exit(asyncio.run(run(args.concurrency, args.total, args.path, use_real, base_url, api_key)))


if __name__ == "__main__":
    main()
