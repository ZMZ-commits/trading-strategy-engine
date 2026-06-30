"""Sandbox worker — runs a PUBLISHED indicator against bars supplied by the caller.

Runs INSIDE the isolated sandbox container. The backend POSTs ``{slug, bars,
params}``; this loads the registry's ``compute.py`` (written by ``publish()``),
executes it to obtain the ``compute`` function, and returns ``run_indicator()``'s
series. No data fetching and no network egress happen here — the backend supplies
the bars.

Executing user-authored code is exactly why this runs in the locked-down sandbox
container rather than in-process in the backend.

NOTE: no ``from __future__ import annotations`` here on purpose — FastAPI must see
``RunRequest`` (defined at module scope) as a real Pydantic model so it treats it
as the request body, not a query parameter.
"""
import json
import os
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel

from .runner import run_indicator


def _registry_base(registry: "Path | None" = None) -> Path:
    """Registry root WITHOUT creating it (the sandbox mounts it read-only)."""
    if registry is not None:
        return Path(registry)
    return Path(os.getenv("TSP_REGISTRY", str(Path.home() / "tsp-registry")))


def load_compute(slug: str, registry: "Path | None" = None):
    """Load and exec a published indicator's source; return (compute_fn, meta)."""
    base = _registry_base(registry) / slug
    meta_path = base / "meta.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"indicator '{slug}' not found")
    meta = json.loads(meta_path.read_text())
    source = (base / "compute.py").read_text()
    namespace: dict = {}
    exec(compile(source, f"<tsp:{slug}>", "exec"), namespace)  # user code; sandboxed
    entry = meta.get("entrypoint", "compute")
    fn = namespace.get(entry)
    if not callable(fn):
        raise ValueError(f"entrypoint '{entry}' not found in published '{slug}'")
    return fn, meta


def execute_published(slug: str, bars: Any, params: "dict | None" = None,
                      registry: "Path | None" = None) -> dict:
    """Load published ``slug`` and run it over ``bars``; returns series + meta."""
    fn, meta = load_compute(slug, registry)
    result = run_indicator(fn, bars, params if params is not None else (meta.get("params") or {}))
    result["meta"] = {"name": meta.get("name"), "slug": slug, "kind": meta.get("kind")}
    return result


def _strategies_base(registry: "Path | None" = None) -> Path:
    """Authoring strategies live alongside the registry, under ../strategies."""
    return _registry_base(registry).parent / "strategies"


def load_strategy_ns(slug: str, registry: "Path | None" = None) -> dict:
    """Exec a strategy's strategy.py and return its module namespace."""
    src = _strategies_base(registry) / slug / "strategy.py"
    if not src.exists():
        raise FileNotFoundError(f"strategy '{slug}' not found")
    namespace: dict = {}
    exec(compile(src.read_text(), f"<tsp-strategy:{slug}>", "exec"), namespace)  # sandboxed
    return namespace


def execute_strategy(slug: str, bars: Any, registry: "Path | None" = None) -> dict:
    """Run a strategy's compute (for its plotted line) and signals (markers).

    Returns run_indicator's ``{"indicators": {...}}`` plus a ``signals`` list of
    ``{"time": iso, "type": "buy"|"sell", "price": float}``.
    """
    ns = load_strategy_ns(slug, registry)
    compute = ns.get("compute")
    if not callable(compute):
        raise ValueError(f"strategy '{slug}' has no compute(ctx)")
    result = run_indicator(compute, bars)

    signals = []
    sig_fn = ns.get("signals")
    if callable(sig_fn):
        for s in sig_fn(bars):
            ts = s.get("ts")
            time = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
            signals.append({"time": time, "type": s.get("type"), "price": s.get("price")})
    result["signals"] = signals
    result["meta"] = {"slug": slug, "kind": "strategy"}
    return result


def list_strategies(registry: "Path | None" = None) -> list:
    """List strategy folders: [{slug, name}, ...]."""
    base = _strategies_base(registry)
    if not base.exists():
        return []
    return [{"slug": d.name, "name": d.name} for d in sorted(base.iterdir()) if d.is_dir()]


def list_published(registry: "Path | None" = None) -> list:
    """List published indicators in the registry: [{slug, name, kind}, ...]."""
    base = _registry_base(registry)
    if not base.exists():
        return []
    out = []
    for d in sorted(base.iterdir()):
        meta = d / "meta.json"
        if d.is_dir() and meta.exists():
            try:
                m = json.loads(meta.read_text())
            except Exception:
                continue
            out.append({"slug": m.get("slug", d.name), "name": m.get("name"), "kind": m.get("kind")})
    return out


class RunRequest(BaseModel):
    slug: str
    bars: list[dict]
    params: dict = {}


class StrategyRequest(BaseModel):
    slug: str
    bars: list[dict]


def create_app():
    """Build the FastAPI worker app (imported lazily so the SDK needn't depend on FastAPI)."""
    from fastapi import FastAPI, HTTPException

    app = FastAPI(title="tsp sandbox worker", version="0.1.0")

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    @app.get("/indicators")
    def indicators_list() -> dict:
        return {"indicators": list_published()}

    @app.post("/run")
    def run(req: RunRequest) -> dict:
        try:
            return execute_published(req.slug, req.bars, req.params)
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:  # noqa: BLE001 — surface author errors to the caller
            raise HTTPException(status_code=400, detail=f"execution error: {e}")

    @app.get("/strategies")
    def strategies_list() -> dict:
        return {"strategies": list_strategies()}

    @app.post("/strategy")
    def strategy(req: StrategyRequest) -> dict:
        try:
            return execute_strategy(req.slug, req.bars)
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:  # noqa: BLE001 — surface author errors to the caller
            raise HTTPException(status_code=400, detail=f"execution error: {e}")

    return app
