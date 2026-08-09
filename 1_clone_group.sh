#!/usr/bin/env bash
# Mirror-clone every repo in a GitLab group (full history) into $WORK/clones.
# Token is passed via header (never persisted into repo configs).
set -euo pipefail
: "${GITLAB_TOKEN:?}"; : "${GITLAB_GROUP:?}"
GITLAB_HOST="${GITLAB_HOST:-https://gitlab.com}"
WORK="${WORK:-./work}"; CLONES="$WORK/clones"; mkdir -p "$CLONES"

GROUP_ENC=$(python3 -c "import urllib.parse,os;print(urllib.parse.quote(os.environ['GITLAB_GROUP'],safe=''))")
page=1; : > "$WORK/repos.txt"
while :; do
  resp=$(curl -s --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
    "$GITLAB_HOST/api/v4/groups/$GROUP_ENC/projects?include_subgroups=true&per_page=100&page=$page&archived=false")
  n=$(printf '%s' "$resp" | python3 -c 'import sys,json;d=json.load(sys.stdin);print(len(d) if isinstance(d,list) else 0)')
  [ "$n" -eq 0 ] && break
  printf '%s' "$resp" | python3 -c 'import sys,json;[print(p["path_with_namespace"]) for p in json.load(sys.stdin)]' >> "$WORK/repos.txt"
  page=$((page+1))
done
echo "projects found: $(wc -l < "$WORK/repos.txt")"

clone_one() {
  local ns="$1" name dest
  name=$(echo "$ns" | tr '/' '_'); dest="$CLONES/$name.git"
  if git -C "$dest" rev-parse --git-dir >/dev/null 2>&1 && [ "$(git -C "$dest" show-ref | wc -l)" -gt 0 ]; then
    echo "[skip] $name"; return
  fi
  rm -rf "$dest"
  git -c http.extraHeader="PRIVATE-TOKEN: $GITLAB_TOKEN" clone --mirror -q "$GITLAB_HOST/$ns.git" "$dest" \
    && echo "[ok] $name refs=$(git -C "$dest" show-ref|wc -l) commits=$(git -C "$dest" rev-list --all --count)" \
    || echo "[FAIL] $name"
}
export -f clone_one; export GITLAB_TOKEN GITLAB_HOST CLONES
xargs -P 4 -I{} bash -c 'clone_one "{}"' < "$WORK/repos.txt"

# Integrity gate: assert refs>0 AND commits>0 (a killed clone leaves objects but no refs).
bad=0
while read -r ns; do
  d="$CLONES/$(echo "$ns" | tr '/' '_').git"
  [ "$(git -C "$d" show-ref 2>/dev/null | wc -l)" -gt 0 ] && \
  [ "$(git -C "$d" rev-list --all --count 2>/dev/null)" -gt 0 ] || { echo "INCOMPLETE: $ns"; bad=$((bad+1)); }
done < "$WORK/repos.txt"
echo "=== clone gate: $bad incomplete (re-run to fix) ==="
