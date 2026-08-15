"""ORB with a chandelier (ATR) trailing exit.

Same entry as `orb-trailing-exit` -- the first close above the 15-minute
opening range -- but the stop hangs from the HIGHEST HIGH REACHED SINCE ENTRY,
minus a volatility cushion of `atr_mult` x ATR(14). Hence "chandelier": it
hangs down from the ceiling of the trade.

Why this exists alongside the swing-low version: swing-low scored higher on
the sample (+8.79R vs +7.51R across five instruments) but only at exactly a
10-bar lookback -- 5, 20 and 30 bars all degrade badly. Chandelier holds
between +6R and +7.5R across ATR multiples of 2.5, 3.0 and 3.5. A result that
survives its own parameter moving is worth more than a higher one that does
not, because next month's best parameter is not knowable today.

The practical difference: swing-low tracks price STRUCTURE and sits flat for
long stretches; chandelier tracks VOLATILITY and glides, tightening
automatically as the market calms.

LONG ONLY -- the engine's tracker models one long position, so a short leg
would report inverted P&L. Downside breaks are skipped rather than mis-scored.
"""
import pandas as pd

from tsp import Ctx

RTH_OPEN, RTH_CLOSE = 9 * 60 + 30, 16 * 60


def compute(ctx: Ctx):
    or_minutes = int(ctx.param("or_minutes", 15))
    atr_n = int(ctx.param("atr_length", 14))
    atr_mult = float(ctx.param("atr_multiple", 3.0))
    max_trades = int(ctx.param("max_trades_per_day", 1))
    last_entry_min = int(ctx.param("last_entry_minute", 14 * 60 + 30))
    cut_failed = bool(ctx.param("failed_breakout_exit", True))

    df = ctx.df
    try:
        local = df.index.tz_convert("America/New_York")
    except (TypeError, AttributeError):
        local = df.index

    # ATR(14) as a simple mean of true range. min_periods=1 so the first bars
    # of the series still produce a usable value instead of NaN, which would
    # otherwise leave the stop undefined on the earliest trades.
    prev_close = df["close"].shift(1)
    true_range = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = true_range.rolling(atr_n, min_periods=1).mean().tolist()

    n = len(df)
    hi_line = [float("nan")] * n
    lo_line = [float("nan")] * n
    trail_line = [float("nan")] * n

    or_end = RTH_OPEN + or_minutes
    day = None
    or_hi = or_lo = None
    taken = 0

    entry = stop = risk = peak = 0.0
    in_trade = False
    wins = losses = 0

    for bar in ctx.bars():
        t = local[bar.i]
        d = t.date()
        m = t.hour * 60 + t.minute

        if d != day:
            if in_trade:
                # Fresh every day: never carry a position overnight.
                ctx.sell(bar.open)
                in_trade = False
                ctx.log("flattened at the next open")
            day, or_hi, or_lo, taken = d, None, None, 0

        if not (RTH_OPEN <= m < RTH_CLOSE):
            continue

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
            # Stop checked before anything else: when a single bar spans both
            # the stop and a new high, booking the loss is the honest reading
            # of a 1-minute bar, since the order within it is unknowable.
            if bar.low <= stop:
                ctx.sell(stop)
                r = (stop - entry) / risk if risk > 0 else 0.0
                if stop > entry:
                    wins += 1
                else:
                    losses += 1
                ctx.log(f"chandelier stop {stop:.2f}  ({r:+.2f}R)")
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
            # Hangs from the trade's ceiling. Ratchet-only: a trailing stop
            # that can fall would keep handing back gains it already secured.
            stop = max(stop, peak - atr_mult * atr[bar.i])
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
    ctx.plot("Chandelier Stop", pd.Series(trail_line, index=df.index), kind="overlay")

    total = wins + losses
    if total:
        ctx.log(f"— {wins}/{total} trades closed green ({100.0 * wins / total:.0f}%)")
