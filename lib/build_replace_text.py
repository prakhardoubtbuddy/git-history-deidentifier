#!/usr/bin/env python3
"""Collect literal secrets from gitleaks JSON reports and write a git-filter-repo
--replace-text list. Structured provider formats are skipped (handled generically
by blob_cb.py); obvious false positives (placeholders, short/multi-word) are dropped.

Usage:
  build_replace_text.py --reports <dir> --out <replace-text.txt> [--merge <existing.txt>]
"""
from __future__ import annotations
import argparse, glob, json, os, re

STRUCTURED = re.compile(
    r'-----BEGIN|sk-ant-|sk-proj-|^sk-[A-Za-z0-9]{32}|EAAA|AKIA[0-9A-Z]{16}|'
    r'AIza[0-9A-Za-z_\-]{35}|gh[pousr]_[A-Za-z0-9]{36}|xox[baprs]-|'
    r'(?:sk|rk)_live_|^SK[0-9a-f]{32}$|^AC[0-9a-f]{32}$|'
    r'eyJ[A-Za-z0-9_\-]{10,}\.eyJ')

def is_fp(s: str) -> bool:
    if not s or len(s) < 12:
        return True
    low = s.lower()
    if any(t in low for t in ("example.com", "redacted", "placeholder", "your_",
                              "xxxx", "changeme", "dummy", "sample", "localhost",
                              "test-", "0000000000")):
        return True
    if " " in s:
        return True
    return False

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reports", required=True, help="dir of gitleaks *.json reports")
    ap.add_argument("--out", required=True, help="output replace-text file")
    ap.add_argument("--merge", default="", help="optional existing replace-text to merge/dedup")
    a = ap.parse_args()

    secrets = set()
    for rp in glob.glob(os.path.join(a.reports, "*.json")):
        try:
            data = json.load(open(rp))
        except Exception:
            continue
        for f in data:
            sec = (f.get("Secret") or "").strip()
            if not sec or is_fp(sec) or STRUCTURED.search(sec):
                continue
            secrets.add(sec)

    new_lines = [f"{s}==>REDACTED_SECRET" for s in sorted(secrets)
                 if "==>" not in s and "\n" not in s]

    combined, seen = [], set()
    src = []
    if a.merge and os.path.exists(a.merge):
        src += [l.rstrip("\n") for l in open(a.merge) if l.strip()]
    for l in src + new_lines:
        if l not in seen:
            seen.add(l); combined.append(l)
    open(a.out, "w").write("\n".join(combined) + ("\n" if combined else ""))
    print(f"reports parsed: {len(glob.glob(os.path.join(a.reports,'*.json')))} | "
          f"unique literals: {len(secrets)} | out lines: {len(combined)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
