# AI_CONTEXT — trading-strategy-engine

> Per-repo living context for AI assistants. Overall system:
> `trading-strategy-platform/docs/ARCHITECTURE.md`. Read that + this, then
> recompute the newest branch (`docs/AI_ONBOARDING.md` §2).
> **Live git state always wins over this snapshot.**
>
> **Last synced:** 2026-06-13 · **Newest branch at sync:** `main` (fully promoted)

---

## 1. What this repo is

The **strategy execution engine** — a small Python package (`trading_strategy_engine`)
that the backend **imports in-process** (not a deployed service). It runs a
strategy, records a run, and reports status, persisting to the same filesystem
strategy store the backend uses.

- **Install:** `pip install -e .` (or pinned via the backend's `requirements.txt`)
- **Public API:** `from trading_strategy_engine import run_strategy, get_status`
- **Note:** the `README.md` still describes the old `src/{strategies,execution,risk}`
  scaffold; the real package is `trading_strategy_engine/`.

---

## 2. Branches & environments

| Env | Branch | Deployed? |
|-----|--------|-----------|
| Production | `main` | No — library, pip-installed by backend |
| Staging | `staging` | No |
| Dev | `dev` | No |

CI workflows (`deploy-{dev,staging,prod}.yml`) exist but this is a package, not a
running service. It ships by being a dependency of the backend image.

---

## 3. Functions & modules (what the code does)

### `trading_strategy_engine/__init__.py`
- Re-exports `run_strategy`, `get_status`.

### `trading_strategy_engine/runner.py`
- `run_strategy(strategy_id, config, store_path)` → `RunResult`. Finds the
  strategy dir, creates `runs/`, writes a `running` draft, then a `completed`
  `RunResult` with one initialization `Transaction`; updates the strategy's
  `lastRunAt`/`lastRunStatus`/`transactions` in `strategy.json`.
  **Currently a stub** — it records a run lifecycle but contains no real trading
  logic yet (the place to add signals/orders/backtests).
- `get_status(strategy_id, store_path)` → latest `RunResult` (newest file in
  `runs/`), else an `idle` result.
- `_find_strategy_dir` — locates the strategy dir by id within the store.

### `trading_strategy_engine/models.py`
- `Transaction` (signal/order/error), `RunResult` (run_id, state, timestamps,
  transactions, notifications), `RunConfig`. `StrategyStatus` =
  `idle|running|completed|error`.

### `trading_strategy_engine/strategies/base.py`
- `BaseStrategy(ABC)` with abstract `run(config) -> RunResult` — the extension
  point for concrete strategies.

---

## 4. Features
- Pydantic run/transaction models shared in shape with the backend.
- Filesystem run persistence compatible with the backend's strategy store.
- Abstract base class for pluggable strategies.
- **Gap:** no concrete strategy implementations or real execution/risk logic yet.

---

## 5. Latest Changes (Living)
> Prepend newest first. Recompute: `git log origin/main --no-merges --oneline`.

- **2026-06-11** (`main`) — add GHCR docker login to VM deploy step.
- **2026-06-10** (`main`) — add Dockerfile + 3-env GitHub Actions CI/CD (Hetzner).
- **2026-06-09** (`main`) — 3-tier branching docs.
- **2026-05-24** (`main`) — implement engine package: models, runner, base strategy.

## 6. What's next / TODO
- Implement real strategy logic (signals → orders → run results) behind `BaseStrategy`.
- Wire concrete strategies into `runner.run_strategy` instead of the stub lifecycle.
- _(add upcoming work here)_
