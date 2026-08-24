#!/usr/bin/env bash
# Authoritative gate: gitleaks over every STAGED delivery repo. Reports any repo
# with residual findings so you can triage (most are FPs: UUIDs in SQL dumps,
# doc placeholders, the REDACTED_* markers themselves, test fixtures).
set -euo pipefail
WORK="${WORK:-./work}"; REPOS="$WORK/delivery/repos"; OUT="$WORK/verify"; mkdir -p "$OUT"
for d in "$REPOS"/*/; do
  name=$(basename "$d")
  gitleaks detect --source "$d" --report-format json --report-path "$OUT/$name.json" \
    --no-banner --redact=0 --exit-code 0 >/dev/null 2>&1 || true
  n=$(python3 -c "import json;print(len(json.load(open('$OUT/$name.json'))))" 2>/dev/null || echo ERR)
  [ "$n" = "0" ] && echo "[clean] $name" || echo "[review] $name: $n"
done
