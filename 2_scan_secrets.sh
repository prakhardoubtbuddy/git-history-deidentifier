#!/usr/bin/env bash
# gitleaks full-history secret scan over every mirror; then build the redaction list.
set -euo pipefail
WORK="${WORK:-./work}"; CLONES="$WORK/clones"; OUT="$WORK/reports"; mkdir -p "$OUT"
HERE="$(cd "$(dirname "$0")" && pwd)"

for d in "$CLONES"/*.git; do
  name=$(basename "$d" .git)
  gitleaks detect --source "$d" --report-format json --report-path "$OUT/$name.json" \
    --no-banner --redact=0 --exit-code 0 >/dev/null 2>&1 || true
  echo "[scanned] $name: $(python3 -c "import json;print(len(json.load(open('$OUT/$name.json'))))" 2>/dev/null || echo ERR)"
done

python3 "$HERE/lib/build_replace_text.py" --reports "$OUT" --out "$WORK/replace-text.txt" \
  ${MERGE_REPLACE_TEXT:+--merge "$MERGE_REPLACE_TEXT"}
echo "redaction list -> $WORK/replace-text.txt"
