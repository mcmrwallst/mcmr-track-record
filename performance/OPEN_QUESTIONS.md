# Open checks — registry

**All resolved, 2026-11-20.** Every published entry, exit and stop was checked
against daily data exported by the owner (`performance/prices/`):

| Check | Result |
|---|---|
| Every entry and exit price inside that day's low–high | Pass, all 9 fills |
| No stop traded before its exit | Pass (ZN 109'00'0 first reached on CME trade date 5 Aug, matching the exit) |
| T003 stop on 3 Sep gapped? | No: opened 7686.71, below the stop |
| ZB contract | ZBU26: both published prices traded in it |
| Month-end marks | Recorded in `performance/marks.csv` |

Remaining for every future month-end: add the close of each open position to
`marks.csv` and extend the daily price file.
