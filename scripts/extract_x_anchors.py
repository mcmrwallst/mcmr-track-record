#!/usr/bin/env python3
"""
extract_x_anchors.py — derive independent time anchors from X post IDs.

WHY THIS EXISTS
---------------
X (Twitter) post IDs are "snowflake" identifiers: the creation time is encoded
inside the number itself. Shift the ID right by 22 bits and add X's epoch
(1288834974657 ms) and you get the millisecond the post was created, on X's
servers.

That matters here because trade files in this ledger cite X threads. A commit
containing a link to post P cannot have existed before P did — so P's timestamp
is a hard LOWER BOUND on that commit, set by a third party, derived from the
ID alone.

This is independent of GitHub entirely. It survives the post being deleted and
the account being suspended, because the time is in the identifier, not the
page.

    py scripts\\extract_x_anchors.py

Writes receipts/x_post_anchors.json. No third-party packages required.
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

OUT = os.path.join("receipts", "x_post_anchors.json")
SNOWFLAKE_EPOCH_MS = 1288834974657          # X/Twitter epoch: 2010-11-04 01:42:54.657 UTC
ID_RE = re.compile(r'(?:x|twitter)\.com/([A-Za-z0-9_]+)/status/(\d{15,25})')


def git(args):
    try:
        return subprocess.run(["git"] + args, capture_output=True,
                              text=True, check=True).stdout
    except FileNotFoundError:
        sys.exit("`git` is not on your PATH. Run this from Git Bash, or install Git for Windows.")
    except subprocess.CalledProcessError as e:
        sys.exit(f"git {' '.join(args)} failed:\n{e.stderr}")


def snowflake_to_utc(post_id: str):
    """Decode an X post ID to its creation time."""
    ms = (int(post_id) >> 22) + SNOWFLAKE_EPOCH_MS
    return datetime.fromtimestamp(ms / 1000, timezone.utc)


def introducing_commit(post_id: str):
    """The first commit that added this post ID to the repository."""
    out = git(["log", "-S", post_id, "--reverse", "--format=%H%x1f%cI%x1f%s", "--all"])
    for line in out.splitlines():
        if line.strip():
            sha, iso, subject = line.split("\x1f", 2)
            return sha, datetime.fromisoformat(iso).astimezone(timezone.utc), subject
    return None, None, None


def main():
    if not os.path.isdir(".git"):
        sys.exit("Run this from the repository root.")

    history = git(["log", "-p", "--all"])
    found = {}
    for handle, post_id in ID_RE.findall(history):
        found.setdefault(post_id, handle)

    if not found:
        print("No X post links found anywhere in this repository's history.")
        return

    anchors = []
    for post_id, handle in sorted(found.items()):
        published = snowflake_to_utc(post_id)
        sha, cdate, subject = introducing_commit(post_id)

        entry = {
            "post_id": post_id,
            "handle": handle,
            "url": f"https://x.com/{handle}/status/{post_id}",
            "published_utc": published.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "derivation": (
                f"({post_id} >> 22) + {SNOWFLAKE_EPOCH_MS} = "
                f"{(int(post_id) >> 22) + SNOWFLAKE_EPOCH_MS} ms since the Unix epoch"
            ),
        }

        if sha:
            delta = (cdate - published).total_seconds()
            entry["referenced_by_commit"] = sha
            entry["commit_subject"] = subject
            entry["commit_date_client"] = cdate.strftime("%Y-%m-%dT%H:%M:%SZ")
            entry["commit_cannot_predate"] = entry["published_utc"]
            entry["commit_claims_to_be_after_post_by_seconds"] = int(delta)
            entry["consistent"] = delta >= 0
            if delta < 0:
                entry["warning"] = (
                    "This commit's claimed date is EARLIER than a post it references, "
                    "which is impossible. The commit date is wrong."
                )
        anchors.append(entry)

    doc = {
        "_what_this_is": (
            "Independent time anchors derived from X post IDs cited in this "
            "ledger. An X post ID encodes its own creation time, assigned by X's "
            "servers and not settable by the account holder."
        ),
        "_what_this_proves": (
            "A commit that references post P cannot have been created before P "
            "existed. Each anchor therefore fixes a hard LOWER BOUND on the "
            "referencing commit, from a source unconnected to GitHub or to this "
            "repository. Where a commit's claimed date sits only minutes after "
            "the post it cites, the two corroborate each other."
        ),
        "_what_this_does_NOT_prove": (
            "It does not establish the post's CONTENT — only that a post with "
            "that identifier was created at that time. It does not prove a commit "
            "was made at its claimed time; it rules out the commit being made "
            "EARLIER, not later. Upper bounds come from the push receipts in this "
            "directory."
        ),
        "_how_to_verify": (
            "Take any post_id below and compute (id >> 22) + 1288834974657. The "
            "result is milliseconds since the Unix epoch. This needs no X account, "
            "no API access, and works even if the post or account is gone, because "
            "the timestamp is inside the identifier itself."
        ),
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "anchor_count": len(anchors),
        "anchors": anchors,
    }

    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)
        fh.write("\n")

    print(f"Wrote {OUT}\n")
    for a in anchors:
        print(f"  post {a['post_id']}")
        print(f"    published (X servers):  {a['published_utc']}")
        if "referenced_by_commit" in a:
            gap = a["commit_claims_to_be_after_post_by_seconds"]
            human = (f"{gap}s" if abs(gap) < 120 else
                     f"{gap // 60}m {gap % 60}s" if abs(gap) < 7200 else
                     f"{gap / 3600:.1f}h")
            flag = "" if a["consistent"] else "   <-- IMPOSSIBLE, commit date is wrong"
            print(f"    cited by commit:        {a['referenced_by_commit'][:8]}  "
                  f"{a['commit_subject'][:44]}")
            print(f"    commit claims:          {a['commit_date_client']}  "
                  f"({human} after the post){flag}")
        else:
            print("    not currently referenced by any commit")
        print()


if __name__ == "__main__":
    main()
