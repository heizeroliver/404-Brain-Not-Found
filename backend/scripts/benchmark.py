#!/usr/bin/env python3
"""Throughput benchmark for the Kate Foresight daily pass (rules + arbitration).

    cd backend
    JWT_SECRET=x DEMO_PASSWORD=y APP_ENV=dev ../.venv/bin/python scripts/benchmark.py 10000 [--narrate]

Generates N synthetic customers in memory (fixed seed, same generator and special
mix as data/generate.py), validates them into Customer objects, then times the
full daily pass per customer: run_rules + arbitrate(record=False). No LLM calls.
--narrate adds template narration (no LLM) for the top-ranked moment.
"""
from __future__ import annotations

import argparse
import importlib.util
import logging
import os
import platform
import random
import statistics
import sys
import time
from datetime import date
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("JWT_SECRET", "benchmark-only-not-a-secret")
os.environ.setdefault("DEMO_PASSWORD", "benchmark")
os.environ.setdefault("APP_ENV", "dev")
logging.getLogger("foresight.store").setLevel(logging.ERROR)

from engine.arbitrate import arbitrate  # noqa: E402
from engine.models import Customer  # noqa: E402
from engine.rules import run_rules  # noqa: E402
from store import Store  # noqa: E402

SEED = 20260930
TODAY = date(2026, 9, 30)
PORTFOLIO = 2_300_000
WORKERS = 32


def load_generator():
    spec = importlib.util.spec_from_file_location("kate_generate", BACKEND / "data" / "generate.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build_customers(n: int) -> list[dict]:
    gen = load_generator()
    rng = random.Random(SEED)
    specials = (["income_drop"] * 7 + ["child_18"] * 6 + ["first_home"] * 8 + ["idle_cash"] * 12 +
                ["capital_gains"] * 8 + ["renovation"] * 6 + ["company_car"] * 8)
    out = []
    for i in range(1, n + 1):
        slot = (i - 1) % 200  # repeat the demo's special mix per block of 200
        special = specials[slot] if slot < len(specials) else None
        out.append(gen.generate_customer(rng, i, special))
    return out


def fmt_duration(seconds: float) -> str:
    if seconds < 120:
        return f"{seconds:.1f} s"
    if seconds < 7200:
        return f"{seconds / 60:.1f} min"
    return f"{seconds / 3600:.2f} h"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("n", nargs="?", type=int, default=10000, help="number of customers (default 10000)")
    ap.add_argument("--narrate", action="store_true", help="include template narration of the top moment")
    args = ap.parse_args()

    narrate_fn = None
    if args.narrate:
        from engine.narrate import template_narration
        narrate_fn = template_narration

    t0 = time.perf_counter()
    raw = build_customers(args.n)
    t_gen = time.perf_counter() - t0
    t0 = time.perf_counter()
    customers = [Customer.model_validate(c) for c in raw]
    t_val = time.perf_counter() - t0
    del raw

    store = Store(Path("/nonexistent/customers.json"), None)  # empty in-memory store, no file I/O

    per_ms: list[float] = []
    detected = delivered_now = care_suppressed = cap_queued = advisor = care_customers = 0
    customers_with_now = 0
    start = time.perf_counter()
    for c in customers:
        t = time.perf_counter()
        moments = run_rules(c, TODAY)
        result = arbitrate(c, moments, TODAY, store, record=False)
        if narrate_fn is not None and result.ranked:
            narrate_fn(result.ranked[0].moment, c)
        per_ms.append((time.perf_counter() - t) * 1000.0)

        detected += len(moments)
        care_customers += result.care_mode
        now = [r for r in result.ranked if r.delivery == "now"]
        delivered_now += len(now)
        customers_with_now += bool(now)
        cap_queued += sum(r.delivery == "queued" for r in result.ranked)
        advisor += sum(r.channel == "advisor" for r in result.ranked)
        care_suppressed += sum(d["reason"].startswith("vulnerability guard") for d in result.decisions)
    total = time.perf_counter() - start

    n = len(customers)
    rate = n / total
    mean_ms = statistics.fmean(per_ms)
    p95_ms = statistics.quantiles(per_ms, n=100)[94] if n >= 2 else per_ms[0]
    single = PORTFOLIO / rate

    print("Kate Foresight daily-pass benchmark")
    print(f"  python           {platform.python_version()} ({platform.python_implementation()})")
    print(f"  cpu count        {os.cpu_count()}  machine={platform.machine()}  os={platform.system()}")
    print(f"  seed / today     {SEED} / {TODAY.isoformat()}")
    print(f"  narration        {'template (top moment)' if narrate_fn else 'not included'}; LLM calls: 0")
    print(f"  setup            generate {t_gen:.2f} s, validate {t_val:.2f} s (not in timing)")
    print("measured")
    print(f"  customers                      {n}")
    print(f"  total seconds                  {total:.3f}")
    print(f"  customers / second             {rate:,.0f}")
    print(f"  per customer ms (mean / p95)   {mean_ms:.3f} / {p95_ms:.3f}")
    print(f"  moments detected               {detected}")
    print(f"  moments delivered now          {delivered_now}  (customers with >=1: {customers_with_now})")
    print(f"  dropped by care mode (sales)   {care_suppressed}")
    print(f"  queued by frequency cap        {cap_queued}")
    print(f"  advisor handoffs (ranked)      {advisor}")
    print(f"  care-mode customers            {care_customers}")
    print(f"extrapolated (linear, from this run) to {PORTFOLIO:,} customers")
    print(f"  single process                 {fmt_duration(single)}")
    print(f"  {WORKERS} parallel workers            {fmt_duration(single / WORKERS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
