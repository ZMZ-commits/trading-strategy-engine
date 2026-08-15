# Strategies

Source of truth for the strategies running on the platform.

At runtime the sandbox loads strategies from a **mounted volume**
(`$TSP_REGISTRY/../strategies/<slug>/strategy.py`), not from this repo — they
are uploaded through the backend's `POST /workspace/scaffold` endpoint or
edited in the web IDE. That volume is shared across dev, staging and
production, so **editing a strategy there changes it in production too.**

Nothing reads these files at runtime. They are here so the strategies are
version-controlled, reviewable and restorable, which the volume alone does not
give you. Keep them in step with what is deployed.

## What's here

| Slug | Entry | Exit |
|---|---|---|
| `opening-range-breakout` | Breakout → retest → rejection candle | Fixed stop, `rr` × risk target |
| `orb-trailing-exit` | First close above the opening range | Stop trailed under the 10-bar low |
| `orb-chandelier-exit` | First close above the opening range | Stop hung from the peak, less `atr_multiple` × ATR |

All three are **long only**: the engine's trade tracker models one long
position (buy then sell), so a short leg would report inverted P&L. Downside
breaks are skipped rather than mis-scored.

## Measured results

Swept across `^GSPC`, `IWM`, `IJR`, `JEPQ` and `AAPL` — 1-minute bars, roughly
18 sessions each, one trade per day, risk-normalised to R:

| Exit | Total R | Positive on |
|---|---:|---:|
| Swing-low trail (`orb-trailing-exit`) | +8.79 | 5/5 |
| Chandelier ATR×3 (`orb-chandelier-exit`) | +7.51 | 4/5 |
| Fixed 3R target (`opening-range-breakout`) | −8.18 | 1/5 |

Swing-low posts the higher number but only at exactly a 10-bar lookback; 5, 20
and 30 all degrade badly. Chandelier holds between +6R and +7.5R across ATR
multiples of 2.5–3.5. **A result that survives its own parameter moving is
worth more than a higher one that does not**, which is why the chandelier
version exists alongside the swing-low one.

Sample sizes are small (~61 trades total). These numbers are a reason to keep
testing, not a reason to trade.
