# receipts/

Evidence of *when*, as opposed to the dates written inside the commits
themselves. See [../VERIFICATION.md](../VERIFICATION.md) for why the two differ
and why only these count.

## What's in here

**`<commit-sha>.json`** — GitHub's server-side record of when that commit
arrived at github.com. Written by a GitHub-hosted runner on GitHub's clock, not
by the repository owner's machine. The field `received_by_github_utc` is the
evidential one; `commit_date_client` is included only so the two can be
compared.

**`<commit-sha>.json.ots`** — an OpenTimestamps proof of the file above,
anchored to the Bitcoin blockchain. Verifies without trusting GitHub, this
account, or anyone else:

```bash
pip install opentimestamps-client
ots verify receipts/<commit-sha>.json.ots
```

A freshly created proof is *pending* for a few hours until it is committed into
a Bitcoin block. A scheduled workflow upgrades pending proofs weekly.

**`push_receipts_backfill.json`** — a one-time capture of GitHub's push events
for commits made before automatic receipting began, pulled from the public
Events API while they were still within its retention window.

## Confirming these independently

Every receipt here corresponds to a public `PushEvent` in GitHub's event stream,
which is mirrored permanently by [GH Archive](https://www.gharchive.org/) — a
third party with no connection to this account. To confirm a receipt without
relying on this repository at all, query GH Archive for the hour named in
`received_by_github_utc` and look for a `PushEvent` on
`mcmrwallst/mcmr-track-record` carrying the commit SHA in question.

That mirror is permanent. GitHub's own public Events API retains roughly 90
days, which is precisely why these receipts are captured into the repository
instead of being left where they expire.

## Why the commit SHA is enough

A git commit hash covers the commit's full tree and its parent. Proving that a
single SHA existed at time *T* therefore proves that every file in the
repository, in exactly its published form, existed at time *T*. One proof per
commit covers the whole ledger at that point in its history.
