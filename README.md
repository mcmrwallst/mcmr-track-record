# MCMR Track Record

Timestamped documentation of discretionary macro trades.

**Purpose:** Every trade decision (open, update, exit) is committed to this repo
at the time the decision is made, BEFORE or simultaneous with any public post.
GitHub's server-side commit timestamps provide independent, third-party proof
of when each call was made.

## Rules of the ledger

1. **Commit first, post second.** The git push happens before (or at the same
   time as) any public post about the trade.
2. **Never edit a past trade file.** Corrections get a new dated file or an
   UPDATE entry. The history must stay append-only — that is what makes it
   credible.
3. **One file per trade event** in `/trades`, named:
   `YYYY-MM-DD_TICKER_ACTION.md`
   Examples:
   - `2026-07-22_ES_OPEN.md`
   - `2026-07-25_ES_UPDATE.md`
   - `2026-07-30_ES_EXIT.md`
4. **Archives** (X data export, screenshots, broker statements) go in
   `/archives` — committing them stamps the date you possessed them.

## Why this works as evidence

- Each `git commit` records a timestamp.
- Pushing to GitHub records the push on GitHub's servers — a timestamp you
  cannot retroactively fake.
- The public commit history shows the full sequence of calls, wins AND losses,
  with no ability to quietly delete the bad ones.

## Structure

```
mcmr-track-record/
├── README.md
├── trades/          # one file per trade event
├── archives/        # X archive zip, screenshots, statements
└── templates/       # blank templates to copy from
```
