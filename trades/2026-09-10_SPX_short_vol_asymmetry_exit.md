# SPX — Short | Exit 2026-09-10

**Status:** Closed
**Instrument:** SPX500
**Direction:** Short
**Entry timestamp:** 2026-09-03 19:30:43 UTC
**Exit timestamp:** 2026-09-10 19:46:23 UTC
**Holding period:** 7 days
**Prior expression:** SPX short, 2026-09-02, closed −1.00R

\---

## Levels

|Field|Value|
|-|-|
|Entry|7751.14|
|Working stop|7793.20 — never moved|
|Stop distance, % of price|0.543% (\~0.68x ATR14)|
|Risk|1.11% of equity (1R)|
|Exit|7593.71|
|Captured|157.43 pts = 2.03% of index|

## Result

**+3.74R = +4.15% of equity.**

Reported in R against 7793.20 as published at entry. Not netted against the prior −1.00R.

|Expression|R|% of equity|
|-|-|-|
|#1|−1.00R|−1.99%|
|#2|+3.74R|+4.15%|
|**Cumulative**|**+2.74R**|**+2.16%**|

\---

## Thesis: worked

Compressed implied volatility producing downside asymmetry.

**VIX \~15 at entry → 18 at exit.** Volatility expanded off the compressed base as the thesis required, and the index gave up 2.03% over seven sessions.

The compressed base is also what made the position work mechanically: at \~0.68x ATR the stop was affordable only because vol was low, and that tight stop is what converted a 2% index move into 3.74R. That is the asymmetry, and it behaved as stated.

**Noted for the conclusion post:** the position was expressed linearly, so the entire result came from direction. The vol expansion confirmed the call but contributed nothing to P\&L — a 15 → 18 move carries real value for a vega-bearing expression and none for a short index position. The thesis is right; the expression does not harvest the part of it that is right.

\---

## Exit

|Criterion|Type|Outcome|
|-|-|-|
|7793.20 traded|Hard working order|Not reached|
|Technical signal|Discretionary, defined pre-entry|**Activated — qualifying exit**|

Exited on a criterion published before entry. Stop never moved, no averaging down, no thesis-morphing.

**Factor present but not published as a criterion.** Bonds and indices are moving in positive correlation in the current regime; the concurrent ZB short was closed earlier the same day, and holding the index leg alone would have left a single-leg expression of a regime view no longer carried elsewhere. This contributed to the timing and was not among the published exit criteria. Recorded as unpublished rather than folded into the table.

**This position was never an expression of the bond thesis** and this exit is not derived from it.

\---

*Record maintained at github.com/mcmrwallst/mcmr-track-record. Position disclosure under @mcmrwallst. Contract counts and account values are not disclosed; percentages are of total account equity. **Drafted from the author's own notes and analysis; AI assistance used for wording, structure and verification of figures.***

