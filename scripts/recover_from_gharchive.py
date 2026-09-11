#!/usr/bin/env python3
"""
recover_from_gharchive.py — recover push receipts GitHub's API no longer serves.

WHY THIS EXISTS
---------------
GitHub's event API drops old events — in practice far sooner than its
documented 90 days. Once an event is gone from the API it cannot be recovered
from GitHub at all.

GH Archive (https://www.gharchive.org/) records GitHub's entire public event
stream to hourly files and keeps them permanently. Those files are hosted by a
third party with no connection to this account, which makes them better
evidence than GitHub's own API, not worse.

This script works out which hourly archives could contain the missing pushes,
downloads them, extracts this repository's PushEvents, and writes them beside
the receipts already captured.

USAGE
-----
    py scripts\\recover_from_gharchive.py
    py scripts\\recover_from_gharchive.py --window 3      # search wider

BANDWIDTH WARNING
-----------------
Each hourly archive is roughly 100-250 MB compressed. The script streams and
discards them as it goes, so disk use stays near zero, but it will pull a few
gigabytes over your connection. Run it on wifi, not a phone hotspot. It prints
each hour as it starts so you can stop it at any time with Ctrl+C — progress
already made is saved when it finishes, so if you need to stop, re-run later
and it will skip hours already covered.

No third-party packages required.
"""

import argparse
import gzip
import io
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

DEFAULT_REPO = "mcmrwallst/mcmr-track-record"
EXISTING = os.path.join("receipts", "push_receipts_backfill.json")
OUT_PATH = os.path.join("receipts", "push_receipts_gharchive.json")
BASE = "https://data.gharchive.org"


def run_git(args):
    try:
        return subprocess.run(
            ["git"] + args, capture_output=True, text=True, check=True
        ).stdout
    except FileNotFoundError:
        sys.exit("`git` is not on your PATH. Run this from Git Bash, or install Git for Windows.")
    except subprocess.CalledProcessError as e:
        sys.exit(f"git {' '.join(args)} failed:\n{e.stderr}")


def local_commits():
    """All local commits, as {sha: {'when': datetime UTC, 'subject': str}}."""
    out = run_git(["log", "--pretty=format:%H%x1f%cI%x1f%s"])
    commits = {}
    for line in out.splitlines():
        if not line.strip():
            continue
        sha, iso, subject = line.split("\x1f", 2)
        when = datetime.fromisoformat(iso).astimezone(timezone.utc)
        commits[sha] = {"when": when, "subject": subject}
    return commits


def already_covered():
    """SHAs that already have a receipt from the API backfill."""
    covered = set()
    for path in (EXISTING, OUT_PATH):
        if not os.path.exists(path):
            continue
        try:
            doc = json.load(open(path, encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for ev in doc.get("push_events", []):
            for c in ev.get("commits_covered", ev.get("commits", [])):
                if c.get("sha"):
                    covered.add(c["sha"])
            if ev.get("head"):
                covered.add(ev["head"])
    return covered


def ancestors_of(sha):
    """Every commit reachable from `sha`, inclusive."""
    try:
        out = subprocess.run(["git", "rev-list", sha],
                             capture_output=True, text=True, check=True).stdout
    except subprocess.CalledProcessError:
        return {sha}
    return {line.strip() for line in out.splitlines() if line.strip()}


def attested_by(heads):
    """
    Commits proven to exist by a set of receipted push heads.

    A commit hash covers its parent's hash, so a receipt for any commit
    transitively attests every ancestor of it. This is why a single later
    receipt can cover a long run of earlier commits.
    """
    covered = set()
    for head in heads:
        if head:
            covered |= ancestors_of(head)
    return covered


def hours_to_search(missing, window):
    """
    Hourly archives that could hold the pushes for these commits.

    A push happens at or after its commit, so we search forward from each
    commit's own hour. Searching forward matters: the FIRST push found after a
    commit attests it and everything before it, so the search can stop there.
    """
    hours = set()
    for meta in missing.values():
        base = meta["when"].replace(minute=0, second=0, microsecond=0)
        for offset in range(0, window + 1):
            hours.add(base + timedelta(hours=offset))
    return sorted(hours)


def forward_hours(start: datetime, max_hours: int):
    """Consecutive hourly slots starting at `start`'s hour."""
    base = start.replace(minute=0, second=0, microsecond=0)
    return [base + timedelta(hours=i) for i in range(max_hours)]


def scan_hour(hour: datetime, repo: str):
    """Stream one hourly archive and return this repo's PushEvents."""
    url = f"{BASE}/{hour.year:04d}-{hour.month:02d}-{hour.day:02d}-{hour.hour}.json.gz"
    found = []
    needle = f'"{repo}"'.encode("utf-8")

    req = urllib.request.Request(url, headers={"User-Agent": "mcmr-track-record-recovery"})
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            with gzip.GzipFile(fileobj=resp) as gz:
                for raw in io.BufferedReader(gz, buffer_size=1 << 20):
                    # Cheap bytes test first; JSON parsing every line is far slower.
                    if needle not in raw:
                        continue
                    try:
                        ev = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if ev.get("type") != "PushEvent":
                        continue
                    if ev.get("repo", {}).get("name") != repo:
                        continue
                    payload = ev.get("payload", {})
                    found.append({
                        "event_id": str(ev.get("id")),
                        "received_by_github_utc": ev.get("created_at"),
                        "actor": (ev.get("actor") or {}).get("login"),
                        "ref": payload.get("ref"),
                        "before": payload.get("before"),
                        "head": payload.get("head"),
                        "source": "gharchive",
                        "source_file": url,
                    })
    except urllib.error.HTTPError as e:
        print(f"    unavailable ({e.code})")
        return []
    except urllib.error.URLError as e:
        print(f"    download failed: {e.reason}")
        return []
    return found


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--repo", default=DEFAULT_REPO)
    ap.add_argument("--window", type=int, default=2,
                    help="(unused in forward mode; kept for compatibility)")
    ap.add_argument("--max-hours", type=int, default=36,
                    help="how many hours to search forward from a commit before "
                         "giving up on tightening it (default 36)")
    ap.add_argument("--out", default=OUT_PATH)
    args = ap.parse_args()

    commits = local_commits()
    covered = already_covered()
    missing = {sha: m for sha, m in commits.items() if sha not in covered}

    print(f"Local commits:            {len(commits)}")
    print(f"Already have a receipt:   {len(commits) - len(missing)}")
    print(f"Still missing a receipt:  {len(missing)}")

    if not missing:
        print("\nNothing to recover — every commit already has a receipt.")
        return

    events = {}
    scanned = set()

    # Load anything a previous run already recovered, so re-runs build on it.
    if os.path.exists(args.out):
        try:
            prev = json.load(open(args.out, encoding="utf-8"))
            for ev in prev.get("push_events", []):
                events[ev["event_id"]] = ev
        except (json.JSONDecodeError, OSError):
            pass

    def still_missing():
        heads = {e.get("head") for e in events.values()} | covered
        done = attested_by(heads) | covered
        return {s: m for s, m in commits.items() if s not in done}

    print(f"\nSearching forward from each unattested commit, oldest first.")
    print("The first push found after a commit attests it AND every commit")
    print("before it, so each search stops as soon as it succeeds.")
    print("Ctrl+C stops cleanly; anything found is still written.\n")

    try:
        while True:
            outstanding = still_missing()
            if not outstanding:
                print("\nEverything is attested.")
                break

            # Oldest unattested commit drives the next search.
            sha, meta = min(outstanding.items(), key=lambda kv: kv[1]["when"])
            print(f"\n--- searching for: {sha[:8]}  {meta['when'].isoformat()}"
                  f"  {meta['subject'][:44]}")

            hit = False
            for hour in forward_hours(meta["when"], args.max_hours):
                if hour in scanned:
                    continue
                if hour > datetime.now(timezone.utc):
                    break
                scanned.add(hour)
                print(f"    {hour.strftime('%Y-%m-%d %H:00 UTC')}", flush=True)
                for ev in scan_hour(hour, args.repo):
                    events[ev["event_id"]] = ev
                    print(f"      FOUND push {ev['head'][:8]} at "
                          f"{ev['received_by_github_utc']}")
                    hit = True
                if hit:
                    break

            if not hit:
                print(f"    no push found within {args.max_hours}h of {sha[:8]};"
                      f" giving up on tightening this one")
                covered.add(sha)     # stop it driving the loop forever
    except KeyboardInterrupt:
        print("\nStopped. Writing what was found so far.")

    pushes = sorted(events.values(), key=lambda p: p["received_by_github_utc"] or "")

    # Expand before..head into the commits each push actually delivered.
    newly = set()
    for p in pushes:
        before, head = p.get("before"), p.get("head")
        spec = head if (not before or before == "0" * 40) else f"{before}..{head}"
        try:
            out = subprocess.run(["git", "rev-list", spec],
                                 capture_output=True, text=True, check=True).stdout
            shas = [s.strip() for s in out.splitlines() if s.strip()]
        except subprocess.CalledProcessError:
            shas = [head] if head else []
        p["commits_covered"] = [
            {"sha": s,
             "commit_date_client": commits[s]["when"].isoformat() if s in commits else None,
             "subject": commits[s]["subject"] if s in commits else None}
            for s in shas
        ]
        newly.update(shas)

    doc = {
        "_what_this_is": (
            "Push receipts for this repository recovered from GH Archive, a "
            "permanent third-party mirror of GitHub's public event stream. These "
            "cover commits whose events GitHub's own API no longer serves. "
            "'received_by_github_utc' is GitHub's server-side arrival time as "
            "recorded at the time of the push; it is not settable by the "
            "repository owner, and these records are held by a third party."
        ),
        "_how_to_verify": (
            "Each entry names the exact GH Archive file it came from in "
            "'source_file'. Download that file independently and search it for "
            "the event_id below. Nothing in this repository has to be trusted."
        ),
        "repository": args.repo,
        "captured_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "push_event_count": len(pushes),
        "push_events": pushes,
    }

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)
        fh.write("\n")

    print(f"\nWrote {len(pushes)} recovered push events to {args.out}")

    # Final accounting, counting transitive attestation through the hash chain.
    all_heads = {e.get("head") for e in events.values()} | already_covered()
    proven = attested_by(all_heads)
    unproven = [s for s in commits if s not in proven]

    print(f"\n  ATTESTATION SUMMARY ({len(commits)} commits total)")
    print(f"  proven to exist by a third-party receipt: {len(commits) - len(unproven)}")
    print(f"  not yet attested:                        {len(unproven)}")
    for sha in unproven:
        print(f"    {sha[:8]}  {commits[sha]['when'].isoformat()}  "
              f"{commits[sha]['subject'][:48]}")
    if unproven:
        print("\n  Unattested commits are usually just the most recent ones —"
              "\n  your next push will attest them and everything before them.")


if __name__ == "__main__":
    main()
