import pandas as pd

from tsp import Ctx, run_indicator, indicators, publish


def _bars(n: int = 60) -> pd.DataFrame:
    idx = pd.date_range("2026-01-01", periods=n, freq="D")
    close = pd.Series(range(100, 100 + n), index=idx, dtype=float)
    return pd.DataFrame({
        "timestamp": idx,
        "open": close,
        "high": close + 1,
        "low": close - 1,
        "close": close,
        "volume": 1000,
    })


def test_indicator_math_shapes():
    s = _bars()["close"]
    assert len(indicators.sma(s, 5)) == len(s)
    assert len(indicators.ema(s, 5)) == len(s)
    assert len(indicators.rsi(s)) == len(s)
    line, sig, hist = indicators.macd(s)
    assert len(line) == len(sig) == len(hist) == len(s)


def test_ctx_exposes_series():
    ctx = Ctx(_bars())
    assert len(ctx.close) == 60
    assert ctx.close.iloc[-1] == 159.0
    assert ctx.high.iloc[0] == 101.0


def test_param_default():
    ctx = Ctx(_bars(), {"length": 30})
    assert ctx.param("length") == 30
    assert ctx.param("missing", 7) == 7


def test_run_indicator_emits_overlay_series():
    def compute(ctx):
        ctx.plot("ema21", ctx.ema(ctx.close, 21), kind="overlay")

    out = run_indicator(compute, _bars())
    assert "ema21" in out["indicators"]
    series = out["indicators"]["ema21"]
    assert series["kind"] == "overlay"
    assert len(series["values"]) == 60
    assert len(series["time"]) == 60
    assert series["values"][-1] is not None  # warm by the end of the window


def test_plot_rejects_bad_kind():
    ctx = Ctx(_bars())
    try:
        ctx.plot("x", ctx.close, kind="banana")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_publish_writes_registry(tmp_path, monkeypatch):
    monkeypatch.setenv("TSP_REGISTRY", str(tmp_path))

    def compute(ctx):
        ctx.plot("sma10", ctx.sma(ctx.close, 10))

    dest = publish("My SMA 10", compute, kind="overlay", params={"n": 10})
    assert (dest / "compute.py").exists()
    assert (dest / "meta.json").exists()
    assert dest.name == "my-sma-10"
