"""Execute a user ``compute(ctx)`` and return a chart-ready result.

This is what the backend's sandbox worker calls: it builds a Ctx from live bars,
runs the published compute, and serializes the emitted plots into the same
``{time, values}`` shape the chart already consumes for built-in indicators.
"""
from __future__ import annotations

import math
from typing import Any, Callable

import pandas as pd

from .context import Ctx


def _to_value(x: Any):
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else round(f, 6)


def run_indicator(compute: Callable[[Ctx], None], bars: Any, params: dict | None = None) -> dict:
    """Run ``compute(ctx)`` over ``bars`` and return its indicator series.

    Returns::

        {"indicators": {name: {"kind": "overlay"|"oscillator",
                               "time": [...], "values": [...]}}}
    """
    ctx = Ctx(bars, params)
    compute(ctx)

    if isinstance(ctx.df.index, pd.DatetimeIndex):
        time = [t.isoformat() for t in ctx.df.index]
    else:
        time = list(range(len(ctx.df)))

    out: dict[str, dict] = {}
    for p in ctx.plots:
        out[p["name"]] = {
            "kind": p["kind"],
            "time": time,
            "values": [_to_value(x) for x in list(p["series"])],
        }
    return {"indicators": out}
