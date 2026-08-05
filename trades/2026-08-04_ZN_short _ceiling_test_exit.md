# ZN — Short | 2026-07-22 → 2026-08-04

**Status:** Closed — stopped out
**Instrument:** ZN (CBOT 10-Year U.S. Treasury Note futures)
**Direction:** Short
**Holding period:** 13 calendar days

**Entry REPO:** https://github.com/mcmrwallst/mcmr-track-record/blob/main/trades/2026-07-22\_ZN\_short\_ceiling\_test\_open.md
**Entry post:** @mcmrwallst, 2026-07-23 (thread, 9 parts)

\---

## Levels

|Field|Value|
|-|-|
|Entry|108'14'0|
|Entry timestamp|2026-07-22, 14:30 ET|
|Working stop|109'00'0|
|Exit trigger|109'00'0|
|Exit timestamp|2026-08-04, 22:32 ET|
|Exit mechanism|Stop-limit|

\---

## Result

|Metric|Value|
|-|-|
|Outcome|Full stop-out|
|**R-multiple**|**−1.00R**|
|Account impact|−4.00%|
|Risk-per-trade|4.00% (1R, as published at entry)|
|Notional exposure|\~771% of equity|

## Thesis

Term-premium expansion and inflation in the 10-year sector.

**Thesis outcome: UNTESTED.**

The position was closed by an 18/32 move — \~8.7 bp

The macro view was never given the opportunity to be right or wrong.

\---

## Corrections log

**2026-08-05 — Entry post published risk parameters that did not match the live order.**

The 2026-07-23 thread stated the stop as 109'19'0 in both tweet 1 and tweet 8, with a
"\~15bp rejection" distance attached. The working order was 109'00'0, placed at
inception and never modified. Order history confirms no post-entry modification.

This was a drafting error in the published thread, not a stop moved under pressure.
The distinction matters and is stated explicitly: the pre-commitment in tweet 8 was
honoured at the order level; the failure was that the thread described a different
trade from the one that was on.

**Consequences of the mismatch, stated in full:**

1. Published stop distance (37/32, \~15bp) was 2.06x the live distance (18/32, \~8.7bp).
The \~15bp figure is internally consistent with 109'19'0 at a DV01 near $77, so the
error was consistent throughout the thread rather than a single slip.
2. Because the thread also published "\~4% of book (1R)", any reader backing out
position size from the stated parameters would arrive at roughly **half** the actual
notional. Actual leverage was \~771%; the published parameters imply \~375%.
3. Readers were therefore given a materially understated picture of the risk carried,
in both stop tolerance and leverage.

No prior post has been edited or deleted. The 2026-07-22 thread stands as published;
this entry is the correction of record.

\---

## Notes

I have been suspended on my X account again for inauthentic behaviour. Hence, I won't be able to post the Exit signal temporarily.



*Record maintained at github.com/mcmrwallst/mcmr-track-record. Position disclosure under
@mcmrwallst. Contract counts and account values are not disclosed; percentages are of
total account equity.*

