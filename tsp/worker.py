"""Sandbox worker — runs a PUBLISHED indicator against bars supplied by the caller.

Runs INSIDE the isolated sandbox container. The backend POSTs ``{slug, bars,
params}``; this loads the registry's ``compute.py`` (written by ``publish()``),
executes it to obtain the ``compute`` function, and returns ``run_indicator()``'s
series. No data fetching and no network egress happen here — the backend supplies
the bars.

Executing user-authored code is exactly why this runs in the locked-down sandbox
container (resource-capped, read-only rootfs, no egress) rather than in-process
in the backend.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from .registry import registry_dir
from .runner import run_indicator


def load_compute(slug: str, registry: Path | None = None) -> tuple[Callable, dict]:
    """Load and exec a published indicator's source; return (compute_fn, meta)."""
    base = (registry or registry_dir()) / slug
    meta = json.loads((base / "meta.json").read_text())
    source = (base / "compute.py").read_text()
    namespace: dict[str, Any] = {}
    exec(compile(source, f"<tsp:{slug}>", "exec"), namespace)  # user code; sandboxed
    entry = meta.get("entrypoint", "compute")
    fn = namespace.get(entry)
    if not callable(fn):
        raise ValueError(f"entrypoint '{entry}' not found in published '{slug}'")
    return fn, meta


def execute_published(
    slug: str,
    bars: Any,
    params: dict | None = None,
    registry: Path | None = None,
) -> dict:
    """Load published ``slug`` and run it over ``bars``; returns series + meta."""
    fn, meta = load_compute(slug, registry)
    result = run_indicator(fn, bars, params if params is not None else (meta.get("params") or {}))
    result["meta"] = {"name": meta.get("name"), "slug": slug, "kind": meta.get("kind")}
    return result


def create_app():
    """Build the FastAPI worker app (imported lazily so the SDK needn't depend on FastAPI)."""
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel

    app = FastAPI(title="tsp sandbox worker", version="0.1.0")

    class RunRequest(BaseModel):
        slug: str
        bars: list[dict]
        params: dict = {}

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    @app.post("/run")
    def run(req: RunRequest) -> dict:
        try:
            return execute_published(req.slug, req.bars, req.params)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"indicator '{req.slug}' not found")
        except Exception as e:  # noqa: BLE001 — surface author errors to the caller
            raise HTTPException(status_code=400, detail=f"execution error: {e}")

    return app
