#!/usr/bin/env python3
"""
build_verification.py — regenerate VERIFICATION.md from the actual receipts.

Reads the receipt files in /receipts plus the local git history, works out what
is genuinely proven and how tightly, and writes VERIFICATION.md to match. Run it
after any push that adds receipts, so the document never claims more coverage
than exists.

    py scripts\\build_verification.py

No third-party packages required.
"""

import glob
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

REPO = "mcmrwallst/mcmr-track-record"
OUT = "VERIFICATION.md"
ZERO = "0" * 40


def git(args):
    try:
        return subprocess.run(["git"] + args, capture_output=True,
                              text=True, check=True).stdout
    except FileNotFoundError:
        sys.exit("`git` is not on your PATH. Run this from Git Bash, or install Git for Windows.")
    except subprocess.CalledProcessError as e:
        sys.exit(f"git {' '.join(args)} failed:\n{e.stderr}")


def load_receipts():
    """Every push receipt across all receipt files: [(head, when_utc, source)]."""
    out = []
    for path in sorted(glob.glob(os.path.join("receipts", "*.json"))):
        try:
            doc = json.load(open(path, encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        events = doc.get("push_events")
        if events is None:
            # A per-commit receipt written by the GitHub Actions workflow.
            if doc.get("commit") and doc.get("received_by_github_utc"):
                out.append((doc["commit"], doc["received_by_github_utc"],
                            "GitHub Actions receipt"))
            continue
        for ev in events:
            head, when = ev.get("head"), ev.get("received_by_github_utc")
            if head and when:
                src = "GH Archive" if ev.get("source") == "gharchive" else "GitHub events API"
                out.append((head, when, src))
    return out


def commits():
    out = git(["log", "--pretty=format:%H%x1f%cI%x1f%s"])
    rows = {}
    for line in out.splitlines():
        if not line.strip():
            continue
        sha, iso, subject = line.split("\x1f", 2)
        rows[sha] = {
            "when": datetime.fromisoformat(iso).astimezone(timezone.utc),
            "subject": subject,
        }
    return rows


def ancestors(sha):
    try:
        out = subprocess.run(["git", "rev-list", sha], capture_output=True,
                             text=True, check=True).stdout
    except subprocess.CalledProcessError:
        return {sha}
    return {l.strip() for l in out.splitlines() if l.strip()}


def main():
    if not os.path.isdir("receipts"):
        sys.exit("No receipts/ directory here. Run this from the repository root.")

    rows = commits()
    receipts = load_receipts()

    # Tightest attestation per commit: the earliest receipt whose head has this
    # commit as an ancestor. A commit hash covers its parent's hash, so a
    # receipt for any commit transitively attests everything before it.
    best = {}
    for head, when, src in receipts:
        try:
            when_dt = datetime.fromisoformat(when.replace("Z", "+00:00"))
        except ValueError:
            continue
        for sha in ancestors(head):
            cur = best.get(sha)
            if cur is None or when_dt < cur[0]:
                best[sha] = (when_dt, head, src)

    ordered = sorted(rows.items(), key=lambda kv: kv[1]["when"])
    attested = [s for s, _ in ordered if s in best]
    unattested = [s for s, _ in ordered if s not in best]

    lines = []
    w = lines.append

    w("# Verification")
    w("")
    w("This document states exactly what this repository proves, what it does not")
    w("prove, and how to check both without taking my word for anything. It is")
    w("generated from the receipt files in `/receipts`, not written by hand, so it")
    w("cannot drift out of line with the evidence.")
    w("")
    w(f"*Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} — "
      f"{len(attested)} of {len(rows)} commits attested.*")
    w("")
    w("---")
    w("")
    w("## The two timestamps")
    w("")
    w("A git commit carries two different dates, and they are not equally trustworthy.")
    w("")
    w("**1. The commit date** — written inside the commit object by the machine that")
    w("created it, from that machine's clock. It can be set to any value:")
    w("")
    w("```")
    w('GIT_AUTHOR_DATE="2019-03-04T09:12:00" GIT_COMMITTER_DATE="2019-03-04T09:12:00" \\')
    w('  git commit -m "..."')
    w("```")
    w("")
    w("This is the date github.com displays in the file listing. **It is not evidence.**")
    w("Any repository owner can set it freely, and people routinely do.")
    w("")
    w("**2. The push receipt** — recorded by GitHub's servers when a commit arrives at")
    w("github.com. The person pushing cannot set it. **This is evidence.** Those")
    w("receipts are not stored in a git repository by default; the files in")
    w("[`/receipts`](receipts/) are this ledger's captured copies of them.")
    w("")
    w("## Why one receipt covers many commits")
    w("")
    w("A commit hash is computed over its contents *and its parent's hash*, which is")
    w("computed over *its* parent, and so on. So proving a single commit existed at")
    w("time *T* proves every ancestor of it existed by *T* as well — an ancestor")
    w("cannot be altered or inserted after the fact without changing every hash that")
    w("follows it. The table below therefore gives each commit the earliest receipt")
    w("that covers it, whether that receipt names the commit directly or reaches it")
    w("through the chain.")
    w("")
    w("This also means tightness varies. A commit pushed seconds after it was written")
    w("has a bound measured in seconds. A commit that sat unpushed, or whose own push")
    w("event has since been discarded by GitHub, is bounded by the next receipt after")
    w("it — which may be days or weeks later. Both are real attestation; they are not")
    w("equally strong, and the table does not pretend otherwise.")
    w("")
    w("## Coverage")
    w("")
    w("| Commit | Claimed (UTC) | Proven to exist by | Gap | Source |")
    w("|---|---|---|---|---|")

    for sha, meta in ordered:
        subject = meta["subject"]
        if len(subject) > 46:
            subject = subject[:43] + "..."
        subject = subject.replace("|", "\\|")
        if sha in best:
            when_dt, head, src = best[sha]
            delta = when_dt - meta["when"]
            secs = int(delta.total_seconds())
            if secs < 0:
                gap = "—"
            elif secs < 120:
                gap = f"{secs}s"
            elif secs < 7200:
                gap = f"{secs // 60}m"
            elif secs < 172800:
                gap = f"{secs // 3600}h"
            else:
                gap = f"{secs // 86400}d"
            proven = when_dt.strftime("%Y-%m-%d %H:%M:%SZ")
        else:
            gap = proven = src = "—"
        w(f"| `{sha[:8]}` {subject} | {meta['when'].strftime('%Y-%m-%d %H:%M:%SZ')} "
          f"| {proven} | {gap} | {src} |")

    w("")
    if unattested:
        w(f"**{len(unattested)} commit(s) not yet attested.** These are the most recent")
        w("entries, whose push events have not yet been captured. The next push to this")
        w("repository will attest them and everything before them.")
        w("")

    w("## What this repository proves")
    w("")
    w("**Sequence and content, cryptographically.** Every commit hash covers its")
    w("parent, so the chain fixes the order of entries and the exact content at each")
    w("step. Nothing published here can be altered without changing every subsequent")
    w("hash.")
    w("")
    w("**That the history has not been rewritten.** Rewriting requires a force-push,")
    w("which changes every downstream hash. The receipts record what the chain looked")
    w("like at specific past moments, which makes that check possible after the fact")
    w("rather than only in the moment.")
    w("")
    w("**That commits reached GitHub no later than the times in the table above.**")
    w("Receipts sourced from the GitHub events API are GitHub's own server-side")
    w("records. Receipts sourced from GH Archive come from a permanent third-party")
    w("mirror of GitHub's public event stream, operated by nobody connected to this")
    w("account — each names the exact archive file it came from, so it can be")
    w("re-derived independently.")
    w("")
    w("## What this repository does NOT prove")
    w("")
    w("**That trades were placed, at the prices stated, in the size stated.** Nothing")
    w("here is broker data. Execution and P&L verification is handled separately")
    w("through a broker-linked third party, and that is the only thing that should be")
    w("treated as authoritative on execution.")
    w("")
    w("**That an entry pre-dates the trade it describes, beyond what the table shows.**")
    w("Where the gap column reads in days, the commit is bounded only loosely. Those")
    w("entries are consistent with the record and I believe them accurate, but they")
    w("are not tightly provable and are not presented as if they were.")
    w("")
    w("**That any entry represents skill rather than variance.** The sample is far too")
    w("small for that question to be answerable. The reasoning is what is on offer,")
    w("not the win rate.")
    w("")
    w("## Known departures from the ledger rules")
    w("")
    w("Listed here rather than left for a reader to discover, because a reader who")
    w("finds them unaided will reasonably assume they were meant to stay hidden.")
    w("")
    w("- **Trade files have been edited after first publication.** All such edits are")
    w("  visible via `git log -p -- trades/`. One, commit `3db5d21d`, was made roughly")
    w("  ten hours after publication and **added an invalidation condition to a section")
    w('  headed "posted now so I can\'t move goalposts later."** That contradicts the')
    w("  section's purpose. It was not concealed and is not defended; it is why the")
    w("  ledger rule has since changed to forbid editing a published file at all.")
    w("")
    w("- **Entry timestamps have lagged commit times.** The SPX entry of 2026-09-02 is")
    w("  stamped 19:58:07 UTC in the file and was committed at 21:44:01 UTC — a lag of")
    w("  1h46m. Any entry whose commit post-dates its stated fill documents a decision;")
    w("  it does not prove the decision pre-dated the fill.")
    w("")
    w("- **Author identity is inconsistent across early commits,** which carry differing")
    w("  author names and one placeholder email address. Commits are signed from the")
    w("  setup date onward; earlier ones are not, and their authorship is not")
    w("  cryptographically established.")
    w("")
    w("- **Early push events were nearly lost.** GitHub discards event history far")
    w("  sooner than its documented 90 days. Receipts for July and early August were")
    w("  recovered from GH Archive after GitHub had already dropped them. Coverage")
    w("  before 24 August 2026 is therefore partial, as the gap column shows.")
    w("")
    w("## How to verify, independently")
    w("")
    w("**Check the history has not been rewritten:**")
    w("")
    w("```bash")
    w(f"git clone https://github.com/{REPO}")
    w(f"cd {REPO.split('/')[1]}")
    w("git log --oneline --graph")
    w("git fsck --full")
    w("```")
    w("")
    w("**Read every edit ever made to a trade file:**")
    w("")
    w("```bash")
    w("git log -p --follow -- trades/")
    w("```")
    w("")
    w("**Check a receipt against the third-party mirror.** Open the relevant file in")
    w("`/receipts`, take the `received_by_github_utc` and `event_id`, then fetch the")
    w("GH Archive hour named in `source_file` and search it for that event id. That")
    w("route depends on neither this repository nor this account existing.")
    w("")
    w("**Check a blockchain proof**, for commits stamped by the timestamping workflow:")
    w("")
    w("```bash")
    w("pip install opentimestamps-client")
    w("ots verify receipts/<commit-sha>.json.ots")
    w("```")
    w("")
    w("Nothing has been removed from this history. If a trade went badly, it is still")
    w("in here.")

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    print(f"Wrote {OUT}")
    print(f"  commits:   {len(rows)}")
    print(f"  attested:  {len(attested)}")
    print(f"  unattested:{len(unattested)}")
    tight = sum(1 for s, _ in ordered if s in best
                and (best[s][0] - rows[s]["when"]).total_seconds() < 3600)
    print(f"  of those, bounded within an hour: {tight}")


if __name__ == "__main__":
    main()
