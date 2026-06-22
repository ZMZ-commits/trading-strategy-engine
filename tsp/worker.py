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


class RunRequest(BaseModel):
    slug: str
    bars: list[dict]
    params: dict = {}


def create_app():
    """Build the FastAPI worker app (imported lazily so the SDK needn't depend on FastAPI)."""
    from fastapi import FastAPI, HTTPException

    app = FastAPI(title="tsp sandbox worker", version="0.1.0")

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    @app.post("/run")
    def run(req: RunRequest) -> dict:
        try:
            return execute_published(req.slug, req.bars, req.params)
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:  # noqa: BLE001 — surface author errors to the caller
            raise HTTPException(status_code=400, detail=f"execution error: {e}")

    return app
