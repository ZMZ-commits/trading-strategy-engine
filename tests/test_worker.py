import pandas as pd

from tsp import publish
from tsp.worker import execute_published, load_compute


def _bars(n: int = 40) -> list[dict]:
    idx = pd.date_range("2026-01-01", periods=n, freq="D")
    return [
        {
            "timestamp": idx[i].isoformat(),
            "open": 50.0 + i,
            "high": 51.0 + i,
            "low": 49.0 + i,
            "close": 50.0 + i,
            "volume": 1000,
        }
        for i in range(n)
    ]


def test_execute_published_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("TSP_REGISTRY", str(tmp_path))

    def compute(ctx):
        ctx.plot("sma5", ctx.sma(ctx.close, 5), kind="overlay")

    publish("Round Trip SMA", compute, kind="overlay")
    out = execute_published("round-trip-sma", _bars())

    assert out["meta"]["slug"] == "round-trip-sma"
    assert out["meta"]["kind"] == "overlay"
    assert "sma5" in out["indicators"]
    series = out["indicators"]["sma5"]
    assert len(series["values"]) == 40
    assert series["values"][-1] is not None


def test_load_compute_missing_entrypoint(tmp_path, monkeypatch):
    monkeypatch.setenv("TSP_REGISTRY", str(tmp_path))
    # publish a valid one, then corrupt meta to point at a missing entrypoint
    def compute(ctx):
        ctx.plot("x", ctx.close)

    dest = publish("Bad Entry", compute)
    (dest / "meta.json").write_text('{"entrypoint": "nope", "kind": "overlay"}')
    try:
        load_compute("bad-entry")
        assert False, "expected ValueError"
    except ValueError:
        pass
