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
import glob
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
SEARCH_LOG = os.path.join("receipts", "gharchive_search_log.json")
BASE = "https://data.gharchive.org"


def hour_key(h: datetime) -> str:
    """The GH Archive file name for an hour, used as a cache key."""
    return f"{h.year:04d}-{h.month:02d}-{h.day:02d}-{h.hour}"


def load_search_log():
    """Hours already downloaded on a previous run — never fetch them twice."""
    try:
        doc = json.load(open(SEARCH_LOG, encoding="utf-8"))
        return set(doc.get("hours_searched", []))
    except (json.JSONDecodeError, OSError):
        return set()


def save_search_log(scanned):
    """
    Persist the searched-hours list.

    This is also a record of diligence: it shows which archive hours were
    examined and came back empty, which is itself evidence about when pushes
    did and did not happen.
    """
    os.makedirs(os.path.dirname(SEARCH_LOG) or ".", exist_ok=True)
    with open(SEARCH_LOG, "w", encoding="utf-8") as fh:
        json.dump({
            "_what_this_is": (
                "GH Archive hourly files that have been downloaded and searched "
                "for pushes to this repository. An hour listed here was examined; "
                "if no receipt in /receipts corresponds to it, no push to this "
                "repository occurred during that hour."
            ),
            "hours_searched": sorted(scanned),
        }, fh, indent=2)
        fh.write("\n")


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


def rev_range_local(before, head):
    """Commits delivered by a push, i.e. everything in before..head."""
    if not head:
        return []
    spec = head if (not before or before == "0" * 40) else f"{before}..{head}"
    try:
        out = subprocess.run(["git", "rev-list", spec],
                             capture_output=True, text=True, check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    return [l.strip() for l in out.splitlines() if l.strip()]


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


def forward_hours(start: datetime, max_hours: int, after_hour=None):
    """
    Hourly slots to search, in priority order.

    Always checks the commit's own hour first — a push usually follows its
    commit within seconds, so that single file is the highest-value test there
    is. If `after_hour` is given (a UTC hour), the rest of the search resumes
    from there instead of crawling through the hours in between: useful when
    you know you would not have been posting before a given time of day.
    """
    base = start.replace(minute=0, second=0, microsecond=0)
    if after_hour is None:
        return [base + timedelta(hours=i) for i in range(max_hours)]

    hours = [base]
    resume = base.replace(hour=after_hour)
    if resume <= base:
        resume = base + timedelta(hours=1)
    for i in range(max_hours - 1):
        h = resume + timedelta(hours=i)
        if h not in hours:
            hours.append(h)
    return hours


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
    ap.add_argument("--tighten", type=float, metavar="HOURS",
                    help="also hunt for tighter receipts for commits whose current "
                         "bound is looser than HOURS. Without this, a commit counts "
                         "as done the moment ANY later receipt covers it through the "
                         "hash chain — even if that bound is weeks away. Use "
                         "--tighten 1 to go after every commit not pinned to within "
                         "an hour.")
    ap.add_argument("--only", metavar="SHAS",
                    help="comma-separated commit SHAs (short form fine) to search "
                         "for, ignoring everything else. Use when you already know "
                         "which commits are worth chasing.")
    ap.add_argument("--after", type=int, metavar="UTC_HOUR",
                    help="after checking a commit's own hour, resume the search "
                         "from this UTC hour rather than the hours in between. "
                         "e.g. --after 13 for the US cash open (13:30 UTC).")
    ap.add_argument("--out", default=OUT_PATH)
    args = ap.parse_args()

    if args.after is not None and not 0 <= args.after <= 23:
        sys.exit("--after must be a UTC hour between 0 and 23.")

    commits = local_commits()
    covered = already_covered()

    if args.only:
        wanted = [s.strip().lower() for s in args.only.split(",") if s.strip()]
        chosen = set()
        for prefix in wanted:
            hits = [s for s in commits if s.lower().startswith(prefix)]
            if not hits:
                sys.exit(f"No commit in this repository starts with '{prefix}'.")
            if len(hits) > 1:
                sys.exit(f"'{prefix}' is ambiguous — matches {len(hits)} commits.")
            chosen.add(hits[0])
        # Everything not explicitly asked for is treated as settled.
        covered |= {s for s in commits if s not in chosen}
        print(f"--only: searching for {len(chosen)} commit(s), ignoring the rest.\n")

    missing = {sha: m for sha, m in commits.items() if sha not in covered}

    print(f"Local commits:            {len(commits)}")
    print(f"Already have a receipt:   {len(commits) - len(missing)}")
    print(f"Still missing a receipt:  {len(missing)}")

    if not missing:
        print("\nNothing to recover — every commit already has a receipt.")
        return

    events = {}
    scanned = load_search_log()
    if scanned:
        print(f"{len(scanned)} archive hours already searched on previous runs — "
              f"these will be skipped.")

    # Load anything a previous run already recovered, so re-runs build on it.
    if os.path.exists(args.out):
        try:
            prev = json.load(open(args.out, encoding="utf-8"))
            for ev in prev.get("push_events", []):
                events[ev["event_id"]] = ev
        except (json.JSONDecodeError, OSError):
            pass

    def receipt_pairs():
        """(head, when) for every receipt we currently hold, from any source."""
        pairs = []
        for e in events.values():
            if e.get("head") and e.get("received_by_github_utc"):
                pairs.append((e["head"], e["received_by_github_utc"]))
        for path in sorted(glob.glob(os.path.join("receipts", "*.json"))):
            try:
                doc = json.load(open(path, encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            for ev in doc.get("push_events", []) or []:
                if ev.get("head") and ev.get("received_by_github_utc"):
                    pairs.append((ev["head"], ev["received_by_github_utc"]))
            if doc.get("commit") and doc.get("received_by_github_utc"):
                pairs.append((doc["commit"], doc["received_by_github_utc"]))
        return pairs

    def current_bounds():
        """Tightest attestation time per commit, via the hash chain."""
        best = {}
        for head, when in receipt_pairs():
            try:
                when_dt = datetime.fromisoformat(when.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                continue
            for sha in ancestors_of(head):
                if sha not in best or when_dt < best[sha]:
                    best[sha] = when_dt
        return best

    def delivered_commits():
        """
        Commits whose OWN arriving push we already hold.

        If a receipt's before..head range contains a commit, that receipt records
        the moment the commit actually reached GitHub. No earlier receipt can
        exist for it, so searching forward can only turn up later pushes —
        strictly worse. These are done, however large their gap looks.
        """
        done = set()
        for e in events.values():
            done.update(rev_range_local(e.get("before"), e.get("head")))
        for path in sorted(glob.glob(os.path.join("receipts", "*.json"))):
            try:
                doc = json.load(open(path, encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            for ev in doc.get("push_events", []) or []:
                done.update(rev_range_local(ev.get("before"), ev.get("head")))
            if doc.get("commit"):
                done.add(doc["commit"])
        return done

    def still_missing():
        """
        Commits still worth searching for.

        Default: commits with no receipt at all. With --tighten HOURS, also
        commits whose bound is looser than HOURS *and* whose own arriving push
        we do not already hold — those are the only ones where a better receipt
        can still exist.
        """
        best = current_bounds()
        delivered = delivered_commits()
        out = {}
        for sha, meta in commits.items():
            if sha in covered:
                continue
            bound = best.get(sha)
            if bound is None:
                out[sha] = meta
            elif args.tighten is not None and sha not in delivered:
                gap_h = (bound - meta["when"]).total_seconds() / 3600.0
                if gap_h > args.tighten:
                    out[sha] = meta
        return out

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

            before_bound = current_bounds().get(sha)
            if before_bound is not None:
                gap_d = (before_bound - meta["when"]).total_seconds() / 86400.0
                print(f"    current bound: {before_bound.strftime('%Y-%m-%d %H:%M:%SZ')}"
                      f"  ({gap_d:.1f}d away) — looking for something tighter")

            hit = False
            for hour in forward_hours(meta["when"], args.max_hours, args.after):
                if hour_key(hour) in scanned:
                    print(f"    {hour.strftime('%Y-%m-%d %H:00 UTC')}  (already searched)")
                    continue
                if hour > datetime.now(timezone.utc):
                    break
                print(f"    {hour.strftime('%Y-%m-%d %H:00 UTC')}", flush=True)
                found = scan_hour(hour, args.repo)
                scanned.add(hour_key(hour))
                save_search_log(scanned)      # survive Ctrl+C
                for ev in found:
                    events[ev["event_id"]] = ev
                    print(f"      FOUND push {ev['head'][:8]} at "
                          f"{ev['received_by_github_utc']}")
                    hit = True
                if hit:
                    break

            if hit:
                after = current_bounds().get(sha)
                if after is not None and (before_bound is None or after < before_bound):
                    gap_s = (after - meta["when"]).total_seconds()
                    unit = (f"{int(gap_s)}s" if gap_s < 120 else
                            f"{int(gap_s // 60)}m" if gap_s < 7200 else
                            f"{gap_s / 3600:.1f}h")
                    print(f"    TIGHTENED to {after.strftime('%Y-%m-%d %H:%M:%SZ')}"
                          f"  ({unit} after the commit)")
                else:
                    print("    found a push, but it was not tighter than what we had")
                    covered.add(sha)

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
