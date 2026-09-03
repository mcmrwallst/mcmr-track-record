# SPX — Short | Exit

**Status:** Closed 2026-09-03
**Instrument:** SPX500 (S\&P 500 cash index CFD)
**Direction:** Short
**Entry file:** `2026-09-02\\\_SPX\\\_short\\\_vol\\\_asymmetry\\\_open.md`
**Entry:** 7665.98, 2026-09-02 19:58:07 UTC
**Exit:** 7743.00 working stop, filled — timestamp and fill from platform History 
**Result:** **−1.00R** (−1.99% of equity)

\---

## Levels

|Field|Value|
|-|-|
|Entry|7665.98|
|Working stop|7743.00|
|Exit fill|7743.00 (stop)|
|Stop distance|1.005% of price · 1.25x ATR(14)|
|Planned risk|1.99% of equity (1R)|
|Realised result|−1.00R|

\---

## Which criterion fired

Criterion #1, as published at entry: **7743.00 traded — hard working order, no exceptions.**

The order executed as specified. No discretionary criterion was invoked. No stop was widened,
no size averaged, no thesis substituted. The position was closed by the mechanism published
before it was opened.

\---

## What the outcome says about the thesis

The thesis was that compressed implied volatility produces a downside-asymmetric distribution
in the index. **Volatility did not expand.** It compressed further while the index drifted
higher, and the stop was reached by drift rather than by a volatility event.

This is the declared risk **"compressed vol can stay compressed"** realised as pre-registered.
On the evidence of this position the asymmetry was **not refuted — it was not tested.** No vol
expansion occurred within the window the stop allowed, so the trade produced no information
about whether the thesis is correct.

**Stop construction is a live question, not a settled one.** The position lost 1.005% of price
— not a fractional-ATR shakeout — so this is not the ZN failure repeated. But a stop sized to
one day of range, against a thesis whose trigger has no date, is structurally exposed to
exactly this outcome. If a further expression stops out on drift rather than on a vol event,
the fault is in the expression, not in the market.

\---

## Standing commitments carried forward

Commitment #5 of the entry file — combined risk treatment of the concurrent ZB short — remains
open and is due at the next entry.

\---

*Record maintained at github.com/mcmrwallst/mcmr-track-record. Position disclosure under
@mcmrwallst. Contract counts and account values are not disclosed; percentages are of total
account equity. **Drafted from the author's own notes and analysis; AI assistance used for wording, structure and verification of figures.***

