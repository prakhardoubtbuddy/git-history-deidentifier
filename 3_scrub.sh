#!/usr/bin/env bash
# De-identify every mirror: rewrite history to replace committer identities with
# Contributor N (mailmap) and redact secrets (literal list + generic pattern callback).
# --prune-empty=never --prune-degenerate=never keeps the commit graph EXACT.
set -euo pipefail
WORK="${WORK:-./work}"; CLONES="$WORK/clones"; OUT="$WORK/scrubbed"; mkdir -p "$OUT"
HERE="$(cd "$(dirname "$0")" && pwd)"
MM="$WORK/mailmap.txt"; RT="$WORK/replace-text.txt"; CB=$(cat "$HERE/lib/blob_cb.py")

# Build the mailmap from all clones (extend a prior key if provided via KEY_IN).
python3 "$HERE/lib/build_mailmap.py" --repos-dir "$CLONES" --mailmap "$MM" \
  --key "$WORK/identity-key.json" ${KEY_IN:+--key-in "$KEY_IN"}

MM_ABS=$(readlink -f "$MM"); RT_ABS=$(readlink -f "$RT")
for d in "$CLONES"/*.git; do
  base=$(basename "$d" .git); dest="$OUT/$base"
  rm -rf "$dest"; git clone -q "$d" "$dest"
  ( cd "$dest" && git-filter-repo --force --prune-empty=never --prune-degenerate=never \
      --mailmap "$MM_ABS" --replace-text "$RT_ABS" --blob-callback "$CB" ) >/dev/null 2>&1
  rn=$(git -C "$dest" log --all --format='%an%n%cn' | sort -u | grep -vcE '^Contributor [0-9]+$|^$')
  echo "[scrubbed] $base commits=$(git -C "$dest" rev-list --all --count) resid_names=$rn"
done
