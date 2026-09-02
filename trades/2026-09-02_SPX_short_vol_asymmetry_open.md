# SPX — Short | Entry 2026-09-02

**Status:** Open
**Instrument:** SPX500

**Direction:** Short
**Entry timestamp:** 2026-09-02 19:58:07 UTC
**Entry post:** @mcmrwallst, 2026-09-02
**Concurrent position:** ZB short, open since 2026-08-05 (see `2026-08-05\\\\\\\_ZB\\\\\\\_short\\\\\\\_ceiling\\\\\\\_test\\\\\\\_continued\\\\\\\_entry.md`)

\---

## Levels

|Field|Value|
|-|-|
|Entry|7665.98|
|Working stop|7743.00|
|Stop distance, % of price|1.005%|
|Risk|1.99% of equity (1R)|
|Notional exposure|\~198% of equity|
|Index exposure|\~1.98% of equity per 1% move in the index|

\---

## Thesis

Entry is signal-triggered. The technical trigger is defined pre-entry and is not disclosed;
it is not restated, generalized, or substituted after the fact.

The reason for expressing it now, at this size, is the volatility regime. Implied
volatility is compressed. Compressed vol is not a directional forecast and is not treated
as one here — it is a statement about the shape of the forward distribution. Volatility is
bounded below and unbounded above, and equity drawdown is the dominant transmission channel
of vol expansion. From a low-vol base the distribution of index outcomes is therefore
asymmetric to the downside, independent of what causes the expansion.

This trade takes that asymmetry. It does not forecast the catalyst.

**Horizon.** Short-dated relative to the concurrent rates position. The stop is sized to
daily range, not to a multi-week thesis. The position may extend if the signal continues to
support it; any such extension is logged as an UPDATE at the time it is taken, not claimed
afterward.

The specific details of the technical trigger here will not be disclosed for secrecy.

\---

## Exit criteria

Published at entry. No additions permitted after this commit.

|Criterion|Type|
|-|-|
|7743.00 traded|Hard working order, no exceptions|
|Technical signal|Discretionary, defined pre-entry|

No averaging down. No thesis-morphing. No stop widening.

\---

## Declared risks

**Regime overlap with the live ZB short is one-sided, not symmetric.** The two positions are
not independent and are not a hedge pair. In a policy/supply yield shock — the ZB thesis —
both win: term premium expands and multiples compress. In a growth scare they offset: bonds
bid, ZB short loses, SPX short wins. The scenario that damages both simultaneously is a
disinflationary dovish surprise in which bonds and equities rally together. That is the
correlated tail, it is not diversified away by the two positions being in different asset
classes, and it is recorded here at entry.

**Notional is gap-exposed and the stop cannot price a gap.** At \~198% of equity, the working
order caps loss only in continuous trade. A 2.5% adverse gap is roughly 5% of equity — five
times 1R — and fills through the stop rather than at it. Weekend and session-break exposure
is the live version of this and is a standing decision each Friday, not a default.

**Compressed vol can stay compressed.** Low implied vol is a distribution statement, not a
timing signal, and low-vol regimes have historically persisted far longer than they
intuitively should. The trade can be correct about shape and wrong about window.

**Stop construction is the known repeat failure mode.** The ZN short closed 2026-08-04 at
−1.00R on ordinary session range with no published exit criterion fired. A stop set at 1.25x
daily ATR is coherent for the short horizon declared above, and incoherent if the position
extends. If it extends without the stop being reconsidered on the record, that is the same
error, and it is pre-registered here so it cannot be reclassified as noise afterward.

\---

## Open commitments

1. Outcome reported in R against the 7743.00 working stop, regardless of result.
2. Any extension of horizon beyond the declared short-dated window logged as a dated UPDATE
at the time of the decision.
3. The entry signal remains undisclosed and is not re-characterized post-hoc. No alternative
rationale is substituted for it in the exit file.
4. Combined risk treatment of the concurrent ZB position to be stated explicitly at whichever
comes first: the next entry, or the exit of either leg.

\---

*Record maintained at github.com/mcmrwallst/mcmr-track-record. Position disclosure under
@mcmrwallst. Contract counts and account values are not disclosed; percentages are of total
account equity. **Drafted from the author's own notes and analysis; AI assistance used for wording, structure and verification of figures.***

