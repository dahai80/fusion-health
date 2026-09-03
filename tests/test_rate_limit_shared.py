from __future__ import annotations

import os
import time
from multiprocessing import Pool

from fusion_health.api.middleware import RateLimiter


def _hit(args):
    db, owner, n = args
    os.environ["FUSION_HEALTH_RATE_LIMIT_DB"] = db
    rl = RateLimiter(5)
    results = []
    for _ in range(n):
        results.append(rl.allow(owner))
        time.sleep(0.002)
    return sum(1 for r in results if r)


def test_multi_process_shared_limit(tmp_path):
    db = str(tmp_path / "shared.db")
    os.environ["FUSION_HEALTH_RATE_LIMIT_DB"] = db
    RateLimiter(5)
    del os.environ["FUSION_HEALTH_RATE_LIMIT_DB"]

    per_proc = 10
    with Pool(2) as pool:
        counts = pool.map(_hit, [(db, "owner-shared", per_proc)] * 2)
    total_allowed = sum(counts)
    # rpm=5 window; both processes hit same owner within 60s
    # shared backend must cap near 5, not 10 (per-process)
    assert total_allowed <= 7, f"shared limit broken: {total_allowed} allowed (expected ~5)"
    assert total_allowed >= 5, f"too restrictive: {total_allowed} allowed"


def test_single_process_shared_matches_local(tmp_path):
    db = str(tmp_path / "single.db")
    os.environ["FUSION_HEALTH_RATE_LIMIT_DB"] = db
    try:
        rl = RateLimiter(3)
        assert rl.allow("o") is True
        assert rl.allow("o") is True
        assert rl.allow("o") is True
        assert rl.allow("o") is False
    finally:
        os.environ.pop("FUSION_HEALTH_RATE_LIMIT_DB", None)
