"""Publish an authored indicator into a registry the backend/sandbox can load.

Writes ``<registry>/<slug>/{compute.py, meta.json}``. The registry location is
``$TSP_REGISTRY`` (default ``~/tsp-registry``).

NOTE: in the running platform, publishing is **gated by auth** (a user must be
logged in to publish/save) — that check lives in the backend/UI. This SDK
function is just the authoring-side primitive that writes the artifact.
"""
from __future__ import annotations

import inspect
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


def _slug(name: str) -> str:
    s = re.sub(r"[^\w\s-]", "", name.lower()).strip()
    return re.sub(r"[\s_-]+", "-", s).strip("-")


def registry_dir() -> Path:
    d = Path(os.getenv("TSP_REGISTRY", str(Path.home() / "tsp-registry"))).expanduser()
    d.mkdir(parents=True, exist_ok=True)
    return d


def publish(
    name: str,
    compute: Callable,
    kind: str = "overlay",
    meta: dict | None = None,
    params: dict | None = None,
) -> Path:
    """Register ``compute`` under ``name``; returns the artifact directory."""
    if kind not in ("overlay", "oscillator"):
        raise ValueError("kind must be 'overlay' or 'oscillator'")
    slug = _slug(name)
    if not slug:
        raise ValueError("name must contain at least one alphanumeric character")

    dest = registry_dir() / slug
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "compute.py").write_text(inspect.getsource(compute))
    (dest / "meta.json").write_text(json.dumps({
        "name": name,
        "slug": slug,
        "kind": kind,
        "entrypoint": compute.__name__,
        "params": params or {},
        "meta": meta or {},
        "publishedAt": datetime.now(timezone.utc).isoformat(),
    }, indent=2))
    return dest
