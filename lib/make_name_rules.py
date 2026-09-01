#!/usr/bin/env python3
"""Emit word-boundary regex rules that strip real names from file CONTENTS.

--mailmap fixes commit metadata and nothing else. Real names also sit in test
fixtures, seed data, CHANGELOGs and API docs, and those need --replace-text.

Do NOT write them as literals. --replace-text matches substrings, so a literal
rule `Marsh==>Contributor` rewrites `Marshall` to `Contributorc` and `Advance` to
`Contributornport`. On a real estate that is hundreds of corrupted identifiers,
and the damage is indistinguishable from the name removal you wanted.

git-filter-repo accepts a `regex:` prefix, so anchor every name on \\b:

    regex:(?i)\\b(?:Dana Marsh|Marsh|Calder|...)\\b==>Contributor

One merged alternation, not one rule per name: filter-repo applies each regex to
every blob in turn, so 300 separate rules cost ~9x the wall-clock of a single
alternation over the same estate.

Multi-word names must come FIRST in the alternation. Python alternation is
leftmost-first, so 'Robin Rook' has to be offered before 'Robin' -- which
also lets you keep a name whose surname is an ordinary word ('Rook', 'Frost')
out of the bare-token list while still removing the person.

    ./make_name_rules.py --key work/identity-key.json --out name-rules.txt \\
        --extra Calder --exclude rook
    cat name-rules.txt >> work/replace-text.txt

Always pass --exclude for any surname that is also an ordinary English or code
word, then confirm with 6_verify_names.py that the person is still removed by
the full-name half of the rule.

--extra matters more than it looks. identity-key.json is built from commit
authorship, so it holds only people who committed. The account owner whose name
sits in every seed fixture, a founder quoted in a CHANGELOG, a customer contact
in a test payload -- none of them authored anything, so none of them are in the
key, and a run driven purely off the key leaves every one of them in place.
"""
from __future__ import annotations
import argparse, json, re


def personas(key_path: str) -> dict[str, str]:
    return json.load(open(key_path)).get("personas", {})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", required=True, help="identity-key.json from 3_scrub.sh")
    ap.add_argument("--out", required=True)
    ap.add_argument("--exclude", action="append", default=[],
                    help="a name token that is also an ordinary word; repeatable")
    ap.add_argument("--label", default="Contributor")
    ap.add_argument("--min-token", type=int, default=4)
    ap.add_argument("--extra", action="append", default=[],
                    help="a name to remove that is NOT in the identity key -- the vendor's "
                         "own surname, a founder, a customer contact; repeatable. The key only "
                         "holds people who authored commits, so anyone who merely appears in "
                         "seed data or a CHANGELOG is invisible to it.")
    a = ap.parse_args()

    drop = {x.lower() for x in a.exclude}
    full: set[str] = set()
    tokens: set[str] = set()
    for k in personas(a.key):
        m = re.match(r"^(.*?)\s*<", k.strip())
        name = (m.group(1) if m else k).strip()
        parts = [p for p in name.split() if p.isalpha() and len(p) >= a.min_token]
        if " " in name and len(name) >= 5:
            full.add(name)
        if len(parts) >= 2:
            tokens.update({parts[0], parts[-1]})
    for x in a.extra:                      # names the key cannot know about
        (full if " " in x else tokens).add(x)

    # multi-word first, longest first -- leftmost alternation wins
    ordered = sorted(full, key=lambda s: (-len(s), s)) + \
              sorted((t for t in tokens if t.lower() not in drop), key=lambda s: (-len(s), s))
    if not ordered:
        print("no names found"); return 1

    rule = r"regex:(?i)\b(?:" + "|".join(re.escape(x) for x in ordered) + r")\b==>" + a.label
    open(a.out, "w").write(rule + "\n")
    print(f"full names: {len(full)} | tokens: {len(ordered) - len(full)} "
          f"| excluded: {sorted(drop) or 'none'}")
    print(f"1 merged rule ({len(rule)} chars) -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
