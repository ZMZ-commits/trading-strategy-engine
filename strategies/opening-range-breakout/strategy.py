"""Opening Range Breakout (ORB).

Recreates the classic intraday ORB by hand, bar by bar:

  1. At the open (09:30 ET) the first ``or_minutes`` of trade define the
     OPENING RANGE -- its high and its low. Nothing is traded during it.
  2. A close beyond the range high is the BREAKOUT.
  3. Price must then come back and RETEST that level (trade back into it).
  4. A REJECTION candle off the retest -- one that closes green and back above
     the level -- is the trigger.
  5. Entry on that candle's close, a fixed stop, and a target at ``rr`` times
     the risk. Exit on stop, target, or the close of the session.

The two range levels are plotted, so the chart shows exactly the lines you
would have drawn by hand at 09:45.

LONG ONLY. The engine's trade tracker models one long position (buy then
sell), so a short leg cannot be represented without reporting inverted P&L.
The downside break is therefore skipped rather than silently mis-scored.
"""
import pandas as pd

from tsp import Ctx


def compute(ctx: Ctx):
    or_minutes = int(ctx.param("or_minutes", 15))
    stop_points = float(ctx.param("stop_points", 25.0))
    # "points" reproduces the video's fixed stop; "or_range" sizes the stop to
    # the opening range instead, which travels across instruments of very
    # different price (25 points is a scratch on an index and a third of a
    # small-cap ETF).
    stop_mode = str(ctx.param("stop_mode", "points"))
    rr = float(ctx.param("rr", 3.0))
    retest_bars = int(ctx.param("retest_bars", 45))
    one_trade_per_day = bool(ctx.param("one_trade_per_day", True))

    df = ctx.df
    # Sessions are defined in exchange time; the frame is indexed in UTC, so a
    # naive hour test would drift by one hour across the DST boundary.
    try:
        local = df.index.tz_convert("America/New_York")
    except (TypeError, AttributeError):
        local = df.index

    open_m = 9 * 60 + 30
    close_m = 16 * 60
    or_end_m = open_m + or_minutes

    n = len(df)
    hi_line = [float("nan")] * n
    lo_line = [float("nan")] * n

    cur_day = None
    or_hi = or_lo = None
    stage = "pre"          # pre -> armed -> broke -> retest -> (position) -> done
    broke_i = 0
    traded_today = False
    stop = target = 0.0
    wins = losses = 0

    for bar in ctx.bars():
        t = local[bar.i]
        day = t.date()
        minutes = t.hour * 60 + t.minute

        if day != cur_day:
            # A position must never straddle sessions -- flatten at the first
            # print of the new day rather than carrying overnight risk the
            # strategy never agreed to take.
            if ctx.in_position:
                ctx.sell(bar.open)
                ctx.log("carried position flattened at next open")
            cur_day = day
            or_hi = or_lo = None
            stage = "pre"
            traded_today = False

        if not (open_m <= minutes < close_m):
            continue

        if minutes < or_end_m:
            or_hi = bar.high if or_hi is None else max(or_hi, bar.high)
            or_lo = bar.low if or_lo is None else min(or_lo, bar.low)
            continue

        if or_hi is None:          # session had no opening print
            continue

        if stage == "pre":
            stage = "armed"
            ctx.log(f"{day} opening range {or_lo:.2f} - {or_hi:.2f} "
                    f"(height {or_hi - or_lo:.2f})")

        hi_line[bar.i] = or_hi
        lo_line[bar.i] = or_lo

        if ctx.in_position:
            # Stop is checked before target: when a bar's range covers both,
            # assuming the loss is the honest reading, not the win.
            if bar.low <= stop:
                ctx.sell(stop)
                losses += 1
                ctx.log(f"stopped out {stop:.2f}")
            elif bar.high >= target:
                ctx.sell(target)
                wins += 1
                ctx.log(f"target hit {target:.2f}")
            elif minutes >= close_m - 1:
                ctx.sell(bar.close)
                ctx.log(f"session close exit {bar.close:.2f}")
            continue

        if traded_today and one_trade_per_day:
            continue

        if stage == "armed":
            if bar.close > or_hi:
                stage = "broke"
                broke_i = bar.i
                ctx.log(f"breakout {bar.close:.2f} above {or_hi:.2f}")

        elif stage == "broke":
            if bar.i - broke_i > retest_bars:
                stage = "armed"          # setup went stale; wait for another
            elif bar.low <= or_hi:
                stage = "retest"

        elif stage == "retest":
            # The rejection candle: buyers defended the level on this bar.
            if bar.close > bar.open and bar.close > or_hi:
                entry = bar.close
                risk = stop_points if stop_mode == "points" else (or_hi - or_lo)
                if risk <= 0:
                    stage = "armed"
                    continue
                stop = entry - risk
                target = entry + rr * risk
                ctx.buy(entry)
                traded_today = True
                ctx.log(f"ENTRY {entry:.2f}  stop {stop:.2f}  target {target:.2f}")
            elif bar.close < or_lo:
                stage = "armed"          # broke the whole range the other way

    ctx.plot("ORB High", pd.Series(hi_line, index=df.index), kind="overlay")
    ctx.plot("ORB Low", pd.Series(lo_line, index=df.index), kind="overlay")

    decided = wins + losses
    if decided:
        ctx.log(f"— {wins}/{decided} resolved trades hit target "
                f"({100.0 * wins / decided:.0f}%)")
