# Verification

This document states exactly what this repository proves, what it does not
prove, and how to check both without taking my word for anything. It is
generated from the receipt files in `/receipts`, not written by hand, so it
cannot drift out of line with the evidence.

*Generated 2026-09-11 18:20 UTC — 15 of 16 commits attested.*

---

## The two timestamps

A git commit carries two different dates, and they are not equally trustworthy.

**1. The commit date** — written inside the commit object by the machine that
created it, from that machine's clock. It can be set to any value:

```
GIT_AUTHOR_DATE="2019-03-04T09:12:00" GIT_COMMITTER_DATE="2019-03-04T09:12:00" \
  git commit -m "..."
```

This is the date github.com displays in the file listing. **It is not evidence.**
Any repository owner can set it freely, and people routinely do.

**2. The push receipt** — recorded by GitHub's servers when a commit arrives at
github.com. The person pushing cannot set it. **This is evidence.** Those
receipts are not stored in a git repository by default; the files in
[`/receipts`](receipts/) are this ledger's captured copies of them.

## Why one receipt covers many commits

A commit hash is computed over its contents *and its parent's hash*, which is
computed over *its* parent, and so on. So proving a single commit existed at
time *T* proves every ancestor of it existed by *T* as well — an ancestor
cannot be altered or inserted after the fact without changing every hash that
follows it. The table below therefore gives each commit the earliest receipt
that covers it, whether that receipt names the commit directly or reaches it
through the chain.

This also means tightness varies. A commit pushed seconds after it was written
has a bound measured in seconds. A commit that sat unpushed, or whose own push
event has since been discarded by GitHub, is bounded by the next receipt after
it — which may be days or weeks later. Both are real attestation; they are not
equally strong, and the table does not pretend otherwise.

## Coverage

| Commit | Claimed (UTC) | Proven to exist by | Gap | Source |
|---|---|---|---|---|
| `cde71dbc` Initialize track record ledger: templates, ... | 2026-07-22 08:16:23Z | 2026-07-22 19:33:49Z | 11h | GH Archive |
| `7abda40a` Update 2026-07-22_ES_UPDATE_EXAMPLE.md | 2026-07-22 09:44:42Z | 2026-07-22 19:33:49Z | 9h | GH Archive |
| `2e408074` Create 2026-07-22_ZN_short_ceiling_test.md | 2026-07-22 19:33:45Z | 2026-07-22 19:33:49Z | 4s | GH Archive |
| `3db5d21d` Update 2026-07-22_ZN_short_ceiling_test.md | 2026-07-23 06:06:31Z | 2026-08-24 22:03:38Z | 32d | GitHub events API |
| `cbf4ebc2` Updates and Correction | 2026-07-27 19:30:08Z | 2026-08-24 22:03:38Z | 28d | GitHub events API |
| `5f6ca920` Create 2026-07-22_ZN_short _ceiling_test_ex... | 2026-08-05 09:18:03Z | 2026-08-24 22:03:38Z | 19d | GitHub events API |
| `31bfe91f` ZB short, ceiling test continues | 2026-08-05 10:09:14Z | 2026-08-24 22:03:38Z | 19d | GitHub events API |
| `ab8d507f` This is a Update on ZB position | 2026-08-24 22:03:33Z | 2026-08-24 22:03:38Z | 5s | GitHub events API |
| `d1e2a1b0` Update 2026-08-24_ZB_short_ceiling_test_upd... | 2026-08-24 23:03:15Z | 2026-08-24 23:03:21Z | 6s | GitHub events API |
| `a4050cf4` Create 2026-09-02_SPX_short_vol_asymmetry_o... | 2026-09-02 21:44:01Z | 2026-09-02 21:44:05Z | 4s | GitHub events API |
| `5413626b` Update 2026-09-02_SPX_short_vol_asymmetry_o... | 2026-09-02 21:49:19Z | 2026-09-02 21:49:23Z | 4s | GitHub events API |
| `6d5b964d` Create 2026-09-03_SPX_short_vol_asymmetry_e... | 2026-09-03 20:14:09Z | 2026-09-03 20:14:14Z | 5s | GitHub events API |
| `ce3ebf35` Create 2026-09-03_SPX_short_vol_asymmetry_r... | 2026-09-03 20:40:55Z | 2026-09-03 20:41:01Z | 6s | GitHub events API |
| `5ea054eb` Create 2026-09-10-ZB-short-exit.md | 2026-09-10 16:37:20Z | 2026-09-10 16:37:26Z | 6s | GitHub events API |
| `3d725155` Create 2026-09-10_SPX_short_vol_asymmetry_e... | 2026-09-10 20:12:19Z | 2026-09-10 20:12:23Z | 4s | GitHub events API |
| `a389355e` Update 2026-09-10-ZB-short-exit.md | 2026-09-10 21:09:50Z | — | — | — |

**1 commit(s) not yet attested.** These are the most recent
entries, whose push events have not yet been captured. The next push to this
repository will attest them and everything before them.

## What this repository proves

**Sequence and content, cryptographically.** Every commit hash covers its
parent, so the chain fixes the order of entries and the exact content at each
step. Nothing published here can be altered without changing every subsequent
hash.

**That the history has not been rewritten.** Rewriting requires a force-push,
which changes every downstream hash. The receipts record what the chain looked
like at specific past moments, which makes that check possible after the fact
rather than only in the moment.

**That commits reached GitHub no later than the times in the table above.**
Receipts sourced from the GitHub events API are GitHub's own server-side
records. Receipts sourced from GH Archive come from a permanent third-party
mirror of GitHub's public event stream, operated by nobody connected to this
account — each names the exact archive file it came from, so it can be
re-derived independently.

## What this repository does NOT prove

**That trades were placed, at the prices stated, in the size stated.** Nothing
here is broker data. Execution and P&L verification is handled separately
through a broker-linked third party, and that is the only thing that should be
treated as authoritative on execution.

**That an entry pre-dates the trade it describes, beyond what the table shows.**
Where the gap column reads in days, the commit is bounded only loosely. Those
entries are consistent with the record and I believe them accurate, but they
are not tightly provable and are not presented as if they were.

**That any entry represents skill rather than variance.** The sample is far too
small for that question to be answerable. The reasoning is what is on offer,
not the win rate.

## Known departures from the ledger rules

Listed here rather than left for a reader to discover, because a reader who
finds them unaided will reasonably assume they were meant to stay hidden.

- **Trade files have been edited after first publication.** All such edits are
  visible via `git log -p -- trades/`. One, commit `3db5d21d`, was made roughly
  ten hours after publication and **added an invalidation condition to a section
  headed "posted now so I can't move goalposts later."** That contradicts the
  section's purpose. It was not concealed and is not defended; it is why the
  ledger rule has since changed to forbid editing a published file at all.

- **Entry timestamps have lagged commit times.** The SPX entry of 2026-09-02 is
  stamped 19:58:07 UTC in the file and was committed at 21:44:01 UTC — a lag of
  1h46m. Any entry whose commit post-dates its stated fill documents a decision;
  it does not prove the decision pre-dated the fill.

- **Author identity is inconsistent across early commits,** which carry differing
  author names and one placeholder email address. Commits are signed from the
  setup date onward; earlier ones are not, and their authorship is not
  cryptographically established.

- **Early push events were nearly lost.** GitHub discards event history far
  sooner than its documented 90 days. Receipts for July and early August were
  recovered from GH Archive after GitHub had already dropped them. Coverage
  before 24 August 2026 is therefore partial, as the gap column shows.

## How to verify, independently

**Check the history has not been rewritten:**

```bash
git clone https://github.com/mcmrwallst/mcmr-track-record
cd mcmr-track-record
git log --oneline --graph
git fsck --full
```

**Read every edit ever made to a trade file:**

```bash
git log -p --follow -- trades/
```

**Check a receipt against the third-party mirror.** Open the relevant file in
`/receipts`, take the `received_by_github_utc` and `event_id`, then fetch the
GH Archive hour named in `source_file` and search it for that event id. That
route depends on neither this repository nor this account existing.

**Check a blockchain proof**, for commits stamped by the timestamping workflow:

```bash
pip install opentimestamps-client
ots verify receipts/<commit-sha>.json.ots
```

Nothing has been removed from this history. If a trade went badly, it is still
in here.
