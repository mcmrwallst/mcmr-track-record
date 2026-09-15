# Conclusion — Inflation / Term Premium | Jul–Sep 2026

**Status:** Closed
**Thesis period:** 2026-07-22 → 2026-09-10
**Instruments:** ZN, then ZB
**Scope:** This is the conclusion for the bond thesis only. The concurrent SPX
short was a separate thesis with its own files and is not covered here.

**Files covered:**

- `2026-07-22_ZN_short_ceiling_test_open.md`
- `2026-07-27_ZN_short_ceiling_test_updates.md`
- `2026-08-04_ZN_short _ceiling_test_exit.md`
- `2026-08-05_ZB_short_ceiling_test_continued_entry.md`
- `2026-08-24_ZB_short_ceiling_test_update.md`
- `2026-09-10-ZB-short-exit.md`

This file adds no new analysis and no figures that are not already in the files
above. It states the result, the sequence, and what was right and wrong against
what was published before the outcome was known.

---

## Result

| Expression | Dates | R | % of equity |
|-|-|-|-|
| ZN short | 2026-07-22 → 08-04 | −1.00R | −4.00% |
| ZB short | 2026-08-05 → 09-10 | +4.75R | +9.60% |
| **Cumulative on the thesis** | | **+3.75R** | |

1R was not the same size in both expressions — 4.00% of equity in ZN, 2.02% in
ZB — so the cumulative figure is a sum of R, not a return.

**Reporting-convention discrepancy, recorded rather than resolved silently.** The
07-27 update committed to reporting this trade at the originally published R
regardless of outcome, which would have logged the stop-out as **−0.49R**. The
08-04 exit instead reported **−1.00R against actual risk taken (−4.00% of
equity)**. The exit convention is the one used above and throughout. It is the
harsher of the two for this trade and the less flattering for the cumulative
figure, which is why it stands — but it is a departure from a published
commitment and is not presented as anything else.

---

## Timeline

| Date | Event |
|-|-|
| 2026-07-22 | Short ZN at 108'14'0 (~4.65% 10Y). Thesis published: term-premium expansion and inflation in the 10-year sector, driven by policy and supply rather than a growth scare. Evidence cited for nothing being braced: HY OAS ~270bp, MOVE off multi-year lows, breakevens ~2.3% into a live oil shock. Sub-thesis: the 4.7–5.0% ceiling, defended on every test since Oct 2023, breaks. |
| 2026-07-27 | Hold. Position, risk and stop unchanged. Iran strikes paused, WTI −9.1%, front end rallied on the headline — read as the market treating the Fed as free to cut into a supply-constrained economy. Thesis sharpened on the record: what is being shorted is the assumption that the Fed can truncate a supply shock — *"the premium I'm long isn't inflation, it's doubt about the reaction function."* Also corrected the published stop: 109'00'0 since entry, not 109'19'0. |
| 2026-08-04 | ZN stopped out, **−1.00R**. Closed by an 18/32 move (~8.7 bp) with none of the four published exit criteria fired. Thesis untested; cost attributable to stop construction, not the view. Full corrections log filed with the exit, including the understated risk picture the 07-22 thread gave readers. |
| 2026-08-05 | Same thesis re-expressed in ZB at 110'06'0, stop 110'26'0, risk 2.02% of equity. Declared at entry: stop tolerance narrower in yield terms than the one already taken out by ordinary range, and the notional reduction nominal rather than real — rate exposure rose to ~0.485% of equity per bp. |
| 2026-08-18 | **Ceiling break.** 30-year prints 5.33%, a 19-year high, clearing the band defended since Oct 2023; 10-year 4.75%. US debt crosses $40 trillion, months earlier than forecast. |
| 2026-08-19 → 08-21 | Treasury doubles buybacks to $4bn per operation; 30-year posts its largest daily fall in nearly two years, DXY −0.8% to 99 — then the entire move round-trips inside two sessions. |
| 2026-08-24 | Hold. No change to size, no change to stop. Open **+1.1R**. Falsification level restated: a 30-year sustaining back below 4.7–5.0% means wrong, not early. Larger threat named as the undelivered fiscal consolidation plan, not the buyback. |
| 2026-09-10 | ZB closed at 107'07'0 — **+4.75R / +9.60% of equity**. 36-day hold, 2'31'0 captured (~20 bp on the CTD), stop 110'26'0 unchanged from entry. |

---

## What played out as built

**The ceiling break was the call, and it broke.** 30-year above 5.3% and the
highest since 2007; 10-year ~4.865%, highest since 2023; 2-year ~4.5% through the
top of its two-year range. The move was concentrated in the long end, which is
the signature of a term-premium repricing rather than a general rate move.

**The no-circuit-breaker argument was tested directly and passed.** The thesis
said a yield rise sourced in policy and supply has no flight-to-quality bid to
halt it, because Treasuries are the source of the stress rather than the refuge.
On 08-19 Treasury supplied that missing official bid by hand. It held for 48
hours, against a debt stock that had crossed $40 trillion the day before.

**The falsification level never triggered.** The 30-year did not sustain back
below the band it broke, and held above 5.3% into the exit.

**The inflation leg is the part not claimed here.** It was published at entry as
a second engine that had not started — breakevens ~2.3% into a live oil shock —
and the 07-27 update restated the position as doubt about the reaction function
rather than an inflation-premium trade. Brent at $105 on Strait of Hormuz transit
risk sits among the drivers cited over the holding period, but nothing in the
record shows the breakeven engine started. The result came from the term-premium
leg.

---

## What did not work as built

**The loss came from stop construction, not from the view.** ZN was taken out by
~8.7 bp of ordinary session range with no published exit criterion fired. The
same risk was then declared again at the ZB entry in yield terms — narrower than
the stop that had just failed — which makes it a known repeated exposure rather
than a surprise. It did not cost anything the second time.

**The published risk parameters did not match the live order.** The 07-22 thread
gave a stop 2.06x the real distance, so any reader sizing from the published
figures arrived at roughly half the actual notional (~771% versus ~375% implied).
Corrected on 07-27, logged in full on 08-04, and the reason the ledger rule now
forbids editing a published file at all.

**The ZB stop was never moved across 36 days.** 110'26'0 from entry to exit. That
is the pre-commitment honoured, and it also means no mechanism existed to lock in
open profit at any point in the hold — including through the 08-18 break and the
08-19 round trip.

---

## Standing commitments carried forward

1. Fill price and timestamp for the 2026-08-05 ZB entry remain owed to the
   record. Flagged in the 08-24 update, not supplied at exit.
2. The entry-thesis commit SHA left as a placeholder in
   `2026-09-10-ZB-short-exit.md` is unresolved, against that file's own
   commitment that placeholders would not survive commit. Published files are not
   edited; it is recorded here instead.
3. Where a reporting convention has to be chosen, the convention is fixed before
   the outcome and stated in the entry file — not selected at exit.

---

*Nothing in this file is proof a trade was placed. What is and is not established
by this repository is set out in [VERIFICATION.md](../VERIFICATION.md); execution
and P&L are verified separately through a broker-linked third party. Contract
counts and account values are not disclosed; percentages are of total account
equity.*

***Drafted from the author's own notes and analysis; AI assistance used for
wording, structure and verification of figures.***
