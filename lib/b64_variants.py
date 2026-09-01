#!/usr/bin/env python3
"""Emit base64-encoded variants of each secret so --replace-text can catch them.

A credential embedded in a base64 blob -- a session payload in an API-doc URL,
say -- never appears as plaintext, so neither the literal list built by
build_replace_text.py nor the format regexes in blob_cb.py will ever see it.
gitleaks *does* decode, so it reports a finding that the scrub cannot remove:
you get a repo that keeps failing 5_verify.sh with no visible cause.

Base64 alignment depends on the byte offset of the secret inside the blob, so a
substring has three possible encodings. Emit all three, each trimmed to the part
that does not depend on the surrounding bytes.

    ./b64_variants.py --secrets replace-text.txt --out b64-extra.txt
    cat b64-extra.txt >> replace-text.txt

Feed it every secret gitleaks found, not just the literal list: the structured
formats (AWS, Twilio SID, ...) are deliberately skipped by build_replace_text.py
because blob_cb.py handles them -- but blob_cb only sees plaintext, so encoded
they are covered by nothing at all.
"""
from __future__ import annotations
import argparse, base64, json, glob, os, re

REPLACEMENT = "REDACTED_B64_SECRET"


def b64_variants(s: str) -> set[str]:
    """The three alignment-independent cores of s under base64."""
    out, b = set(), s.encode()
    for pad in (0, 1, 2):
        enc = base64.b64encode(b"\0" * pad + b).decode()
        core = enc[{0: 0, 1: 2, 2: 3}[pad]:]          # drop padding-contaminated head
        if len(core) > 8:
            core = core[: len(core) - (len(core) % 4 or 4)]   # and the dependent tail
        if len(core) >= 16:                            # shorter is too collision-prone
            out.add(core)
    return out


def is_junk(s: str) -> bool:
    if not s or len(s) < 12 or " " in s:
        return True
    low = s.lower()
    return any(t in low for t in ("example.com", "redacted", "placeholder", "your_",
                                  "xxxx", "changeme", "dummy", "sample", "localhost"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--secrets", help="an existing replace-text.txt to read LHS values from")
    ap.add_argument("--reports", help="dir of gitleaks *.json (preferred: includes structured formats)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    secrets: set[str] = set()
    if a.secrets:
        for line in open(a.secrets):
            line = line.rstrip("\n")
            if "==>" in line and not line.startswith(("regex:", "glob:")):
                secrets.add(line.split("==>")[0])
    for rp in glob.glob(os.path.join(a.reports or "", "*.json")) if a.reports else []:
        try:
            data = json.load(open(rp))
        except Exception:
            continue
        for f in data:
            secrets.add((f.get("Secret") or "").strip())

    lines = sorted({f"{v}=={'>'}{REPLACEMENT}"
                    for s in secrets if not is_junk(s)
                    for v in b64_variants(s)})
    with open(a.out, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"secrets considered: {len(secrets)} | base64 rules written: {len(lines)} -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
