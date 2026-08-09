#!/usr/bin/env bash
# Harden the scrubbed repos (strip remotes/reflogs/filter-repo internals, gc-prune),
# verify no residual real names / origin URLs, then tar into a single archive.
set -euo pipefail
WORK="${WORK:-./work}"; SRC="$WORK/scrubbed"; STAGE="$WORK/delivery"; REPOS="$STAGE/repos"
ARCHIVE="${ARCHIVE:-$WORK/delivery.tar.gz}"
rm -rf "$STAGE"; mkdir -p "$REPOS"
VERIFY="$STAGE/VERIFICATION.txt"; MANIFEST="$STAGE/MANIFEST.csv"
echo "repo,commits,authors_ContributorN,size" > "$MANIFEST"; : > "$VERIFY"

for r in "$SRC"/*/; do
  name=$(basename "$r"); dest="$REPOS/$name"
  rsync -a --exclude='.git/filter-repo' --exclude='.git/logs' "$r" "$dest/"
  git -C "$dest" reflog expire --all --expire=now 2>/dev/null || true
  git -C "$dest" remote remove origin 2>/dev/null || true
  git -C "$dest" gc --prune=now --quiet 2>/dev/null || true
  rn=$(git -C "$dest" log --all --format='%an%n%cn' | sort -u | grep -vcE '^Contributor [0-9]+$|^$')
  rem=$(git -C "$dest" remote -v | wc -l)
  commits=$(git -C "$dest" rev-list --all --count)
  authors=$(git -C "$dest" log --all --format='%an' | sort -u | grep -c '^Contributor' || true)
  size=$(du -sh "$dest" | cut -f1)
  echo "$name,$commits,$authors,$size" >> "$MANIFEST"
  st=OK; { [ "$rn" -ne 0 ] || [ "$rem" -ne 0 ] || [ "$commits" -eq 0 ]; } && st=REVIEW
  echo "[$st] $name resid_names=$rn remotes=$rem commits=$commits authors=$authors" | tee -a "$VERIFY"
done

( cd "$STAGE" && tar czf "$ARCHIVE" repos MANIFEST.csv VERIFICATION.txt )
sha256sum "$ARCHIVE" > "$ARCHIVE.sha256"
echo "archive: $ARCHIVE ($(du -h "$ARCHIVE" | cut -f1)) | REVIEW flags: $(grep -c REVIEW "$VERIFY" || echo 0)"
