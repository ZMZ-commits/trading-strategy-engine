"""tsp — authoring SDK for custom indicators (and, later, strategies).

Used inside the JupyterLab kernel to author a ``compute(ctx)`` function, preview
it against real bars, and ``publish`` it. The backend's sandbox worker uses
``run_indicator()`` to execute a published ``compute`` against live data and
return a series the chart renders.

See the platform repo: docs/ROADMAP.md §5 (the tsp SDK contract).

Example (in a notebook)::

    from tsp import Ctx, run_indicator, publish

    def compute(ctx):
        ctx.plot("EMA 21", ctx.ema(ctx.close, ctx.param("length", 21)), kind="overlay")

    # preview against bars you fetched, then publish:
    out = run_indicator(compute, bars, {"length": 21})
    publish("My EMA", compute, kind="overlay", params={"length": 21})
"""
from .context import Ctx
from .runner import run_indicator
from .registry import publish, registry_dir
from . import indicators

__all__ = ["Ctx", "run_indicator", "publish", "registry_dir", "indicators"]
