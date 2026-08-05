# ZB — Short | Entry 2026-08-05

**Status:** Open
**Instrument:** ZB (CBOT 30-Year U.S. Treasury Bond futures)
**Direction:** Short
**Entry post:** @mcmrwallst, 2026-08-05
**Prior expression:** ZN short, 2026-07-22 → 2026-08-04, closed −1.00R (see `2026-07-22\_ZN\_short.md`)

\---

## Levels

|Field|Value|
|-|-|
|Entry|110'06'0|
|Working stop|110'26'0|
|Stop distance, % of price|0.567%|
|Risk|2.02% of equity (1R)|
|Notional exposure|\~356% of equity|
|Rate exposure|\~0.485% of equity per bp|

\---

## Thesis

Unchanged from the 2026-07-22 thread. Term-premium expansion through the 4.7–5.0% ceiling
that has been defended on every test since Oct 2023, with no risk premium and no inflation
premium priced against this test.

Driver remains policy + supply — hawkish Fed, record issuance, bear steepening — not a
growth scare. That distinction is the trade: a yield rise sourced in policy and supply has
no flight-to-quality circuit breaker, because bonds are the source of stress rather than
the refuge. Breakevens near 2.2% into a live oil shock remain a second engine that has not
started.

**Prior expression was not invalidated.** The ZN position closed 2026-08-04 on an 18/32
move (\~8.7 bp) with none of the four published exit criteria fired. That was noise. The
cost was attributable to stop construction, not to the view.

\---

## Instrument change: ZN → ZB

\---

## Exit criteria

Published at entry. No additions permitted after this commit.

|Criterion|Type|
|-|-|
|110'26'0 traded|Hard working order, no exceptions|
|Technical signal|Discretionary, defined pre-entry|

No averaging down. No thesis-morphing. No stop widening.

\---

## Declared risks

**Stop tolerance is narrow relative to thesis horizon.** 4.2 bp of tolerance against a
term-premium thesis whose catalysts run through FOMC and the issuance calendar. This is
narrower in yield terms than the ZN stop that was taken out by ordinary session range
(\~8.7 bp). Recorded at entry so it cannot be claimed as hindsight if it repeats.

**Notional reduction is nominal, not real.** Exposure fell from \~771% (ZN) to \~356% (ZB),
but ZB duration is roughly 2.3x ZN. Rate exposure is \~0.485% of equity per bp versus
\~0.462% previously. The position is marginally *more* exposed to yields than its
predecessor despite the smaller notional figure.

**Reduced management capacity 2026-08-01 → 08-23.** Known at entry. Stop is a live working
order and executes without intervention. Discretionary exit criteria may not be actionable
during this window.

\---

## Open commitments

1. Fill price and timestamp to be entered on execution; placeholders not to survive commit.
2. Any DV01 restatement to be logged, not silently applied.
3. Outcome reported in R against the 20/32 working stop, regardless of result.

\---

*Record maintained at github.com/mcmrwallst/mcmr-track-record. Position disclosure under
@mcmrwallst. Contract counts and account values are not disclosed; percentages are of total
account equity.*

