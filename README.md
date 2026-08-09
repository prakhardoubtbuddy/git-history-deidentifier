# git-history-deidentifier

Score-preserving de-identification of Git repositories for external review.

Given a set of repos (e.g. a GitLab group), it rewrites full history to:

1. **Replace committer identities** with neutral labels (`Contributor 1`, `Contributor 2`, …)
   via a pair-keyed `git-filter-repo --mailmap`. Each distinct real identity gets its own
   number, so the **distinct-author count per repo is preserved** — which keeps
   commit-history-based quality metrics unchanged.
2. **Redact secrets** in two layers:
   - a **literal list** built from a `gitleaks` scan (exact values found), and
   - a **generic pattern callback** (`lib/blob_cb.py`) that neutralises known
     credential *formats* regardless of value (private keys, OpenAI/Anthropic, AWS,
     Google, GitHub, Slack, Stripe live, Square, Twilio, JWTs).

Redaction preserves line counts, and history rewriting uses
`--prune-empty=never --prune-degenerate=never`, so the commit graph and line metrics
stay identical — the repo scores the same before and after.

## Pipeline

```bash
cp config.env.example config.env && edit config.env   # GitLab group + short-lived read token
source config.env

./1_clone_group.sh     # mirror-clone every repo (full history) -> $WORK/clones
./2_scan_secrets.sh    # gitleaks scan -> $WORK/reports, build $WORK/replace-text.txt
./3_scrub.sh           # build mailmap + rewrite history -> $WORK/scrubbed
./4_package.sh         # harden + tar -> $WORK/delivery.tar.gz (+ .sha256)
./5_verify.sh          # gitleaks gate over the staged delivery
```

`KEY_IN=prev/identity-key.json` on `3_scrub.sh` reuses numbering across batches so the
same person keeps the same `Contributor N`. `MERGE_REPLACE_TEXT=prev/replace-text.txt`
on `2_scan_secrets.sh` carries a prior redaction list forward.

## Requirements

`git`, `git-filter-repo`, `gitleaks`, `python3`, `curl`, `rsync`.

## ⚠️ What never leaves this repo

The **outputs** are sensitive and are git-ignored — never commit them:

- `identity-key.json` / `mailmap.txt` — real names ↔ Contributor N (the PII you're removing)
- `replace-text.txt` / `reports/` — **actual secret values** in plaintext
- `clones/` — the **original** repos with live credentials and real names
- `config.env` — your access token

This repository is the **tooling only**. Run it against your own data; keep `work/` local.

## Notes on residual gitleaks findings

After scrubbing, a `gitleaks` re-scan typically still reports matches — these are
false positives, not live secrets: UUIDs inside SQL dumps, doc placeholders
(`YOUR_API_KEY`), the `REDACTED_*` markers this tool inserts, and library test
fixtures. Verify by inspection; the structured provider formats are already gone.
Treat any credential that was real in the original history as **rotated at source**.
