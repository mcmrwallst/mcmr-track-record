#!/usr/bin/env python3
"""
backfill_receipts.py — capture GitHub's server-side push receipts for this ledger.

WHY THIS EXISTS
---------------
A git commit carries two dates, and they are not the same thing:

  1. The commit date, written INSIDE the commit object by the machine that made
     it. Fully settable by whoever runs `git commit`. This is what github.com
     displays in the file listing ("2 months ago"). It is not evidence.

  2. The push receipt, recorded by GitHub's servers when the commit arrived.
     The pusher cannot set it. This IS evidence.

Receipt (2) is not stored in your repository. It lives in GitHub's public event
stream, which is exposed for roughly 90 DAYS and then drops out of reach. This
script pulls those receipts and writes them into the repo, so the evidence
becomes permanent and portable instead of expiring.

Run it once now to capture existing history, then let the GitHub Actions
workflow handle every future push automatically.

USAGE
-----
    python scripts/backfill_receipts.py

Optional but recommended — raises the API rate limit from 60/hr to 5000/hr:
    $env:GITHUB_TOKEN="github_pat_..."    (PowerShell)
    export GITHUB_TOKEN=github_pat_...    (macOS/Linux)

No third-party packages required.

NOTE ON ENDPOINTS
-----------------
This queries the REPOSITORY event feed (/repos/{owner}/{repo}/events) first.
The user feed (/users/{user}/events/public) is capped at 300 events across ALL
of your repositories, so on an active account it will silently fail to reach
back far enough for any one repo. The repo feed is scoped to this repository
alone and reaches much further back for the same cap. Both are queried and the
results merged, so whichever reaches further wins.
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

DEFAULT_USER = "mcmrwallst"
DEFAULT_REPO = "mcmrwallst/mcmr-track-record"
OUT_PATH = os.path.join("receipts", "push_receipts_backfill.json")
API = "https://api.github.com"


def api_get(url: str):
    """GET a GitHub API URL, returning parsed JSON (or None on 404)."""
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "mcmr-track-record-backfill")
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 403:
            sys.exit(
                "\nGitHub API rate limit hit (403).\n"
                "Set a GITHUB_TOKEN environment variable and re-run — see the header of this file.\n"
            )
        if e.code == 404:
            return None
        raise


def _collect(url_template: str, label: str):
    """Page through an events endpoint, returning raw event dicts."""
    events = []
    for page in range(1, 4):          # the feeds serve at most 300 events
        batch = api_get(url_template.format(page=page))
        if batch is None:
            print(f"  {label}: not available (404)")
            return []
        if not batch:
            break
        events.extend(batch)
        if len(batch) < 100:
            break
    print(f"  {label}: {len(events)} events returned")
    return events


def fetch_push_events(user: str, repo: str):
    """Collect PushEvents for `repo` from both the repo feed and the user feed."""
    print("Fetching push events ...")

    raw = []
    raw += _collect(f"{API}/repos/{repo}/events?per_page=100&page={{page}}",
                    "repository feed")
    raw += _collect(f"{API}/users/{user}/events/public?per_page=100&page={{page}}",
                    "user feed")

    by_id = {}
    for ev in raw:
        if ev.get("type") != "PushEvent":
            continue
        if ev.get("repo", {}).get("name") != repo:
            continue
        if ev.get("id") in by_id:
            continue
        payload = ev.get("payload", {})
        by_id[ev.get("id")] = {
            "event_id": ev.get("id"),
            "received_by_github_utc": ev.get("created_at"),
            "actor": ev.get("actor", {}).get("login"),
            "ref": payload.get("ref"),
            "before": payload.get("before"),
            "head": payload.get("head"),
            # GitHub often returns this empty; `head`/`before` are authoritative.
            "commits": [
                {"sha": c.get("sha"), "message": c.get("message")}
                for c in payload.get("commits", [])
            ],
        }

    pushes = sorted(by_id.values(), key=lambda p: p["received_by_github_utc"] or "")
    return pushes


ZERO_SHA = "0" * 40


def rev_range(before: str, head: str):
    """
    Commits introduced by a push, i.e. everything in before..head.

    GitHub's PushEvent payload often carries an empty `commits` array, but
    `before` and `head` are always set. Expanding that range against the local
    clone recovers exactly which commits arrived in that push.
    """
    if not head:
        return []
    spec = head if (not before or before == ZERO_SHA) else f"{before}..{head}"
    try:
        out = subprocess.run(
            ["git", "rev-list", spec],
            capture_output=True, text=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def local_commits():
    """Read local commit dates so the two clocks can be compared side by side."""
    try:
        out = subprocess.run(
            ["git", "log", "--pretty=format:%H%x1f%cI%x1f%s"],
            capture_output=True, text=True, check=True,
        ).stdout
    except FileNotFoundError:
        print(
            "\n  NOTE: `git` was not found on your PATH, so local commit dates\n"
            "  could not be read for comparison. This does not affect the receipts\n"
            "  themselves — they come from GitHub. If you want the comparison, run\n"
            "  this from Git Bash, or install Git for Windows and reopen the terminal.\n"
        )
        return {}
    except subprocess.CalledProcessError:
        print("\n  NOTE: this folder does not look like a git repository;"
              " skipping local comparison.\n")
        return {}

    commits = {}
    for line in out.splitlines():
        if not line.strip():
            continue
        sha, date, subject = line.split("\x1f", 2)
        commits[sha] = {"commit_date_client": date, "subject": subject}
    return commits


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--user", default=DEFAULT_USER)
    ap.add_argument("--repo", default=DEFAULT_REPO)
    ap.add_argument("--out", default=OUT_PATH)
    args = ap.parse_args()

    pushes = fetch_push_events(args.user, args.repo)

    if not pushes:
        print(
            "\nNo push events found for this repository.\n"
            "They may have aged out of GitHub's ~90-day window. Older pushes are\n"
            "still recoverable from the GH Archive mirror — see receipts/README.md.\n"
        )

    locals_ = local_commits()
    covered = set()

    for p in pushes:
        # GitHub frequently returns payload.commits empty. The authoritative
        # fields are `before` and `head`: every commit in the range
        # before..head arrived at GitHub in this push.
        shas = rev_range(p.get("before"), p.get("head"))
        if not shas:
            shas = [c["sha"] for c in p["commits"] if c.get("sha")]
            if not shas and p.get("head"):
                shas = [p["head"]]

        resolved = []
        for sha in shas:
            covered.add(sha)
            entry = {"sha": sha}
            meta = locals_.get(sha)
            if meta:
                entry["commit_date_client"] = meta["commit_date_client"]
                entry["subject"] = meta["subject"]
            resolved.append(entry)
        p["commits_covered"] = resolved
        p.pop("commits", None)

    matched = sum(
        1 for p in pushes for c in p["commits_covered"] if "commit_date_client" in c
    )
    uncovered = [sha for sha in locals_ if sha not in covered]

    doc = {
        "_what_this_is": (
            "GitHub's own server-side record of when each commit was PUSHED to "
            "github.com. 'received_by_github_utc' is set by GitHub and cannot be "
            "set by the repository owner. 'commit_date_client' is the date written "
            "inside the commit object by the author's machine and CAN be set "
            "arbitrarily; it is included only so the two can be compared."
        ),
        "_independently_verifiable_at": (
            "https://www.gharchive.org/ — a permanent third-party mirror of "
            "GitHub's public event stream. Any event below can be located there "
            "by its event_id and timestamp, with no reliance on this repository "
            "or on the account owner."
        ),
        "_coverage_note": (
            "GitHub's public event feeds retain roughly 90 days and are capped at "
            "300 events. Commits older than the earliest receipt below are not "
            "covered by this file; their push times remain recoverable from the "
            "GH Archive mirror but are not attested here."
        ),
        "repository": args.repo,
        "captured_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "push_event_count": len(pushes),
        "commits_matched_to_local_history": matched,
        "local_commits_not_covered": uncovered,
        "push_events": pushes,
    }

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)
        fh.write("\n")

    print(f"\nWrote {len(pushes)} push events to {args.out}")
    if pushes:
        print(f"  earliest receipt: {pushes[0]['received_by_github_utc']}")
        print(f"  latest receipt:   {pushes[-1]['received_by_github_utc']}")
    print(f"  commits with a receipt: {matched}")

    if locals_:
        print(f"  local commits WITHOUT a receipt: {len(uncovered)}")
        if uncovered:
            print("\n  These commits pre-date the available event window:")
            for sha in uncovered:
                print(f"    {sha[:8]}  {locals_[sha]['commit_date_client']}"
                      f"  {locals_[sha]['subject'][:52]}")
            print("\n  They are not attested by this file. Say so in VERIFICATION.md")
            print("  rather than letting a reader assume full coverage.")

    print("\nNow commit it — in GitHub Desktop, or:")
    print(f"  git add {args.out}")
    print('  git commit -m "Capture GitHub push receipts for existing history"')
    print("  git push")


if __name__ == "__main__":
    main()
