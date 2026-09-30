# Kate Foresight: daily-pass benchmark

What is timed: for every customer, the full daily pass `run_rules(customer, today)` followed by
`arbitrate(..., record=False)` (consent filter, care-mode guard, feedback suppression, scoring,
frequency cap, channel choice). Customer generation and Pydantic validation happen before the
timer starts. Narration is off by default; no LLM call is made anywhere in the pass.

## Command

```bash
cd backend
JWT_SECRET=x DEMO_PASSWORD=y APP_ENV=dev ../.venv/bin/python scripts/benchmark.py 10000
# optional: add --narrate to include template narration (no LLM) of the top moment
```

Fixed seed `20260930`, fixed date `2026-09-30`, same generator and special-case mix as
`backend/data/generate.py` (repeated per block of 200 customers).
Machine: CPython 3.11.15, Linux x86_64, 4 CPUs (hackathon cloud container), one process.

## Measured

| Metric | 1,000 customers | 10,000 customers | 10,000 + `--narrate` |
|---|---:|---:|---:|
| Total seconds | 0.167 | 1.316 | 1.701 |
| Customers / second | 5,989 | 7,597 | 5,878 |
| Per customer ms, mean | 0.162 | 0.128 | 0.166 |
| Per customer ms, p95 | 0.280 | 0.210 | 0.268 |
| Moments detected | 1,977 | 19,999 | 19,999 |
| Moments delivered now | 1,035 | 10,412 | 10,412 |
| Customers with at least one moment now | 963 | 9,584 | 9,584 |
| Sales moments dropped by care mode | 10 | 113 | 113 |
| Moments queued by frequency cap | 860 | 8,910 | 8,910 |
| Advisor handoffs (ranked, channel = advisor) | 227 | 2,384 | 2,384 |
| Care-mode customers | 23 | 244 | 244 |

The frequency-cap count is from a cold store (no deliveries recorded earlier in the week), so it is
the within-day cap only.

## Extrapolated (not measured)

Linear extrapolation from the 10,000-customer run to 2,300,000 customers:

| Setup | Extrapolated wall time |
|---|---:|
| Single process | about 5.0 min (6.5 min with template narration) |
| 32 parallel workers | about 9.5 s (12.2 s with template narration) |

The 32-worker figure assumes 32 cores and ignores data loading and fan-out overhead. It was not run
on this 4-CPU machine.

## Production design

- Nightly batch: partition customers by id and fan the daily pass out to N stateless workers; each writes its ranked moments and decision log to the store.
- Event-driven recalculation: re-run a single customer when their data changes (new transaction, consent change, feedback) or when a known deadline enters its window.
- The LLM is called only for wording (narration of the moment actually shown) or for intent parsing; detection, arbitration and care-mode rules stay deterministic.
- So there is no AI call per customer per day: cost scales with moments shown, not with portfolio size.
