"""The execution context handed to a user's ``compute(ctx)``.

Exposes the exported OHLCV metrics as pandas Series, declared params, the
built-in indicator library, and output sinks (``plot`` for indicators).
"""
from __future__ import annotations

from collections import namedtuple
from typing import Any

import pandas as pd

from . import indicators

_OHLCV = ("open", "high", "low", "close", "volume")

# One bar handed to a strategy inside ``for bar in ctx.bars():``.
Bar = namedtuple("Bar", ["i", "ts", "open", "high", "low", "close", "volume"])


def _to_df(bars: Any) -> pd.DataFrame:
    """Accept a DataFrame or an iterable of bar dicts; normalize to OHLCV."""
    df = bars.copy() if isinstance(bars, pd.DataFrame) else pd.DataFrame(list(bars))
    df.columns = [str(c).lower() for c in df.columns]
    if "timestamp" in df.columns:
        # utc=True so ranges that cross a DST boundary (mixed -04:00/-05:00
        # offsets, e.g. 5Y/MAX) don't raise "Mixed timezones detected".
        df = df.set_index(pd.to_datetime(df["timestamp"], utc=True))
    for col in _OHLCV:
        if col not in df.columns:
            df[col] = pd.NA
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


class Ctx:
    """Context passed to ``compute(ctx)``.

    - ``ctx.open/high/low/close/volume`` — exported metrics (pandas Series)
    - ``ctx.param(name, default)`` — declared inputs
    - ``ctx.sma/ema/rsi/macd/bbands/vwap/stoch(...)`` — built-in indicators
    - ``ctx.plot(name, series, kind)`` — emit an indicator series as output
    """

    def __init__(self, bars: Any, params: dict | None = None) -> None:
        self.df = _to_df(bars)
        self.params = dict(params or {})
        self._plots: list[dict] = []
        # trade tracker + console
        self.trades: list[dict] = []   # [{ts, type: 'buy'|'sell', price}]
        self.logs: list[dict] = []     # [{ts, msg}]  -- the P&L console
        self._entry: float | None = None
        self._cur: "Bar | None" = None
        self.last_pnl: float = 0.0

    # ── exported metrics ──
    @property
    def open(self) -> pd.Series: return self.df["open"]
    @property
    def high(self) -> pd.Series: return self.df["high"]
    @property
    def low(self) -> pd.Series: return self.df["low"]
    @property
    def close(self) -> pd.Series: return self.df["close"]
    @property
    def volume(self) -> pd.Series: return self.df["volume"]

    def param(self, name: str, default: Any = None) -> Any:
        return self.params.get(name, default)

    # ── built-in indicator library (default source = close) ──
    def _s(self, series: pd.Series | None) -> pd.Series:
        return self.close if series is None else series

    def sma(self, series: pd.Series | None = None, n: int = 20): return indicators.sma(self._s(series), n)
    def ema(self, series: pd.Series | None = None, n: int = 20): return indicators.ema(self._s(series), n)
    def rsi(self, series: pd.Series | None = None, n: int = 14): return indicators.rsi(self._s(series), n)
    def macd(self, series: pd.Series | None = None, fast: int = 12, slow: int = 26, signal: int = 9):
        return indicators.macd(self._s(series), fast, slow, signal)
    def bbands(self, series: pd.Series | None = None, n: int = 20, k: float = 2.0):
        return indicators.bbands(self._s(series), n, k)
    def vwap(self): return indicators.vwap(self.high, self.low, self.close, self.volume)
    def stoch(self, k: int = 14, d: int = 3): return indicators.stoch(self.high, self.low, self.close, k, d)
    def donchian(self, entry_n: int = 20, exit_n: int = 10):
        return indicators.donchian(self.high, self.low, entry_n, exit_n)

    # ── output sink ──
    def plot(self, name: str, series: pd.Series, kind: str = "overlay") -> None:
        if kind not in ("overlay", "oscillator"):
            raise ValueError("kind must be 'overlay' or 'oscillator'")
        self._plots.append({"name": name, "kind": kind, "series": series})

    @property
    def plots(self) -> list[dict]:
        return self._plots

    # ── trade tracker (one position, one stock) ──────────────────────
    # Iterate the bars and call ctx.buy()/ctx.sell(); the runner turns the
    # recorded trades into the chart's buy/sell markers and the P&L total.
    def bars(self):
        """Yield each bar as ``Bar(i, ts, open, high, low, close, volume)``."""
        for i, (ts, row) in enumerate(self.df.iterrows()):
            self._cur = Bar(i, ts, row["open"], row["high"], row["low"], row["close"], row["volume"])
            yield self._cur

    @property
    def in_position(self) -> bool:
        return self._entry is not None

    def buy(self, price: float | None = None) -> None:
        """Record a buy at the current bar (defaults to its close)."""
        if self._cur is None:
            return
        p = float(self._cur.close if price is None else price)
        self._entry = p
        self.trades.append({"ts": self._cur.ts, "type": "buy", "price": p})

    def sell(self, price: float | None = None) -> None:
        """Record a sell at the current bar (defaults to its close); updates P&L."""
        if self._cur is None or self._entry is None:
            return
        p = float(self._cur.close if price is None else price)
        self.last_pnl = p - self._entry
        self._entry = None
        self.trades.append({"ts": self._cur.ts, "type": "sell", "price": p})

    def log(self, msg: Any) -> None:
        """Print to the strategy's P&L console (shown in the metrics panel)."""
        ts = self._cur.ts if self._cur is not None else None
        self.logs.append({"ts": ts, "msg": str(msg)})

    @property
    def pnl(self) -> float:
        """Realized per-share P&L across completed round-trips."""
        total, entry = 0.0, None
        for t in self.trades:
            if t["type"] == "buy":
                entry = t["price"]
            elif t["type"] == "sell" and entry is not None:
                total += t["price"] - entry
                entry = None
        return round(total, 4)
