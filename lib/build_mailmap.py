#!/usr/bin/env python3
"""Enumerate every distinct committer (name <email>) across a set of git repos and
emit a git-filter-repo --mailmap that maps each to a neutral 'Contributor N'.

Pair-keyed: each distinct real identity gets its own number, so the DISTINCT-AUTHOR
COUNT per repo is preserved exactly (important if you score the repos afterwards).
An existing identity key can be supplied so the same person keeps the same number
across multiple runs/batches.

Usage:
  build_mailmap.py --repos-dir <dir-of-clones> --mailmap out.mailmap \
      --key identity-key.json [--key-in previous-key.json]
The identity key is INTERNAL (maps real -> Contributor N). Never publish it.
"""
from __future__ import annotations
import argparse, json, os, re, subprocess

def committers(repo: str):
    out = subprocess.run(["git", "-C", repo, "log", "--all",
                          "--format=%an <%ae>%n%cn <%ce>"],
                         capture_output=True, text=True).stdout
    return {l for l in out.splitlines() if l.strip()}

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repos-dir", required=True)
    ap.add_argument("--mailmap", required=True)
    ap.add_argument("--key", required=True, help="output identity key JSON (internal)")
    ap.add_argument("--key-in", default="", help="optional prior key to extend")
    a = ap.parse_args()

    per = {}
    if a.key_in and os.path.exists(a.key_in):
        per = json.load(open(a.key_in)).get("personas", {})
    nmax = max([int(re.search(r"(\d+)", v).group(1)) for v in per.values()], default=0)

    ids = set()
    for name in sorted(os.listdir(a.repos_dir)):
        p = os.path.join(a.repos_dir, name)
        if os.path.isdir(p):
            ids |= committers(p)
    for ident in sorted(ids):
        if ident not in per:
            nmax += 1
            per[ident] = f"Contributor {nmax}"

    def newmail(label): return f"contributor{re.search(r'(\d+)', label).group(1)}@example.com"
    lines = []
    for ident, label in sorted(per.items(), key=lambda kv: int(re.search(r"(\d+)", kv[1]).group(1))):
        m = re.match(r"^(.*)\s<([^>]*)>$", ident)
        if m:
            lines.append(f"{label} <{newmail(label)}> {m.group(1)} <{m.group(2)}>")
    open(a.mailmap, "w").write("\n".join(lines) + "\n")
    json.dump({"_note": "INTERNAL identity map (real -> Contributor N). Never publish.",
               "personas": per}, open(a.key, "w"), indent=1)
    print(f"identities: {len(ids)} | personas total: {len(per)} | mailmap lines: {len(lines)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
