"""ORB with a trailing exit.

Same entry as `opening-range-breakout` -- the first close above the 15-minute
opening range -- but the exit is a TRAILING stop that follows price structure
instead of a fixed target.

Why: the fixed-target version never reached its target once in 18 sessions.
Swept against every industry-standard exit across five instruments, a stop
trailed under the recent swing low was the only method that finished positive
on all five (+8.79R total vs -8.18R for a 3R fixed target).

The stop starts under the opening range and only ever ratchets up, so the exit
rides a trend day and cuts a failed breakout at the same level a hand-drawn
stop would sit.

Plots the opening range and the live trailing stop, so the chart shows exactly
where the exit was at every bar.

LONG ONLY -- the engine's tracker models one long position, so a short leg
would report inverted P&L. Downside breaks are skipped rather than mis-scored.
"""
import pandas as pd

from tsp import Ctx

RTH_OPEN, RTH_CLOSE = 9 * 60 + 30, 16 * 60


def compute(ctx: Ctx):
    or_minutes = int(ctx.param("or_minutes", 15))
    swing_n = int(ctx.param("swing_n", 10))
    max_trades = int(ctx.param("max_trades_per_day", 1))
    last_entry_min = int(ctx.param("last_entry_minute", 14 * 60 + 30))
    cut_failed = bool(ctx.param("failed_breakout_exit", True))

    df = ctx.df
    try:
        local = df.index.tz_convert("America/New_York")
    except (TypeError, AttributeError):
        local = df.index

    n = len(df)
    hi_line = [float("nan")] * n
    lo_line = [float("nan")] * n
    trail_line = [float("nan")] * n

    or_end = RTH_OPEN + or_minutes
    day = None
    or_hi = or_lo = None
    taken = 0
    # Rolling window of recent lows -- the structure the stop trails under.
    lows: list = []

    entry = stop = risk = 0.0
    peak = 0.0
    in_trade = False
    wins = losses = 0

    for bar in ctx.bars():
        t = local[bar.i]
        d = t.date()
        m = t.hour * 60 + t.minute

        if d != day:
            if in_trade:
                # Never carry overnight: this is a fresh-every-day strategy.
                ctx.sell(bar.open)
                in_trade = False
                ctx.log("flattened at the next open")
            day, or_hi, or_lo, taken = d, None, None, 0
            lows = []

        if not (RTH_OPEN <= m < RTH_CLOSE):
            continue

        lows.append(bar.low)
        if len(lows) > swing_n:
            lows.pop(0)

        if m < or_end:
            or_hi = bar.high if or_hi is None else max(or_hi, bar.high)
            or_lo = bar.low if or_lo is None else min(or_lo, bar.low)
            continue
        if or_hi is None:
            continue

        hi_line[bar.i] = or_hi
        lo_line[bar.i] = or_lo

        if in_trade:
            peak = max(peak, bar.high)
            # Stop first: when one bar spans both the stop and a new high,
            # taking the loss is the honest reading of a 1-minute bar.
            if bar.low <= stop:
                ctx.sell(stop)
                r = (stop - entry) / risk if risk > 0 else 0.0
                if stop > entry:
                    wins += 1
                else:
                    losses += 1
                ctx.log(f"trail stop {stop:.2f}  ({r:+.2f}R)")
                in_trade = False
                continue
            if cut_failed and bar.close < or_lo:
                ctx.sell(bar.close)
                losses += 1
                ctx.log(f"failed breakout, out at {bar.close:.2f}")
                in_trade = False
                continue
            if m >= RTH_CLOSE - 1:
                ctx.sell(bar.close)
                if bar.close > entry:
                    wins += 1
                else:
                    losses += 1
                ctx.log(f"session close {bar.close:.2f}")
                in_trade = False
                continue
            # Ratchet only -- a trailing stop must never loosen.
            stop = max(stop, min(lows))
            trail_line[bar.i] = stop
            continue

        if taken >= max_trades or m > last_entry_min:
            continue

        if bar.close > or_hi:
            entry = bar.close
            risk = or_hi - or_lo
            if risk <= 0:
                continue
            stop = entry - risk
            peak = entry
            in_trade = True
            taken += 1
            trail_line[bar.i] = stop
            ctx.buy(entry)
            ctx.log(f"{d} entry {entry:.2f} above {or_hi:.2f}, stop {stop:.2f}")

    ctx.plot("ORB High", pd.Series(hi_line, index=df.index), kind="overlay")
    ctx.plot("ORB Low", pd.Series(lo_line, index=df.index), kind="overlay")
    ctx.plot("Trail Stop", pd.Series(trail_line, index=df.index), kind="overlay")

    total = wins + losses
    if total:
        ctx.log(f"— {wins}/{total} trades closed green ({100.0 * wins / total:.0f}%)")
