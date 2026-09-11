# MCMR Track Record

Public, append-only documentation of discretionary macro trades — the thesis
before the trade, the updates during it, and the exit, win or lose.

**Purpose:** Every trade decision (open, update, exit) is committed to this repo
at the time the decision is made, before or simultaneous with any public post.
The point is not the P&L — the sample is far too small for that to mean
anything. The point is that the reasoning is fixed in public before the outcome
is known, so it can be judged on its merits rather than reconstructed
afterwards.

**What this proves, and what it doesn't:** see [VERIFICATION.md](VERIFICATION.md).
Read that before treating any date here as evidence. In short: the commit
history proves sequence, content, and that nothing has been rewritten; the files
in [`/receipts`](receipts/) carry GitHub's own server-side record of when each
commit arrived, independently confirmable via GH Archive; OpenTimestamps proofs
anchor the same to the Bitcoin blockchain. Execution and P&L are verified
separately through a broker-linked third party — nothing in this repository
should be taken as proof a trade was placed.

## Rules of the ledger

1. **Commit first, post second.** The push happens before, or at the same time
   as, any public post about the trade. Where a lag exists between the stated
   entry time and the commit, the lag is stated in the file.
2. **Never edit a published trade file.** Not for typos, not for clarifications,
   not within the hour. Corrections and additions get a new dated UPDATE file
   that references the original. An edit to a published thesis is
   indistinguishable from moving the goalposts, regardless of intent — and the
   diff is permanent and public either way. Past departures from this rule are
   listed in [VERIFICATION.md](VERIFICATION.md) rather than left to be found.
3. **Sign every commit.** Unsigned commits establish no authorship — the author
   field is free text that anyone can set.
4. **One file per trade event** in `/trades`, named
   `YYYY-MM-DD_TICKER_ACTION.md`:
   - `2026-07-22_ES_OPEN.md`
   - `2026-07-25_ES_UPDATE.md`
   - `2026-07-30_ES_EXIT.md`
5. **Losers stay.** Nothing is deleted. A ledger you can prune is a highlight
   reel, and everyone knows it.
6. **Archives** (X data export, screenshots, broker statements) go in
   `/archives` — committing them stamps the date of possession.

## Structure

```
mcmr-track-record/
├── README.md
├── VERIFICATION.md   # what is and isn't proven, and how to check
├── trades/           # one file per trade event
├── receipts/         # GitHub push receipts + OpenTimestamps proofs
├── archives/         # X archive, screenshots, statements
├── templates/
└── scripts/
```

## Verifying this record

```bash
git clone https://github.com/mcmrwallst/mcmr-track-record
cd mcmr-track-record
git log --oneline --graph          # full sequence, nothing pruned
git log -p --follow -- trades/     # every edit ever made to any trade file

pip install opentimestamps-client
ots verify receipts/<commit-sha>.json.ots
```

Full instructions, including how to confirm the push receipts against a
third-party mirror that does not depend on this account existing, are in
[VERIFICATION.md](VERIFICATION.md).
