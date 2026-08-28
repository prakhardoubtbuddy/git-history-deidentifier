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
./6_verify_names.py $WORK/delivery/repos $WORK/clones tokens.txt   # name + syntax gate
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
- `tokens.txt` — the org/project/host names you are removing (a name list is itself PII)

This repository is the **tooling only**. Run it against your own data; keep `work/` local.

## Three leak surfaces, not one

`--mailmap` rewrites **commit metadata only**. Secrets scrubbing (`2_scan_secrets.sh`)
covers **secret values only**. Neither touches org names, project names or internal
hostnames — those need to be handled explicitly, and they hide in three different
places, each requiring a different mechanism:

| surface | mechanism |
|---|---|
| commit messages | `git-filter-repo --replace-message` |
| file contents | `git-filter-repo --replace-text` |
| file paths | `git-filter-repo --filename-callback` |

Enumerate all three **before** the first pass. Discovering them one at a time means one
full history rewrite per discovery, and on a large estate that is hours each.

**Replacements must be hyphen-free.** A name is often substituted *inside* an identifier,
so `acme-corp` produces `class Acmeacme-corpApi` — which no longer parses. Use
`acmecorp`. `6_verify_names.py` runs `php -l` precisely because a name-only check passes
a tree that will not compile.

**A denylist result of CLEAN means "none of the names I thought of".** Scanning for
names you already know cannot find a name nobody told you about. Where the value space
is enumerable -- hostnames especially -- invert it: allowlist what is known-public and
replace *everything else*, recognised or not, with a stable pseudonym. Distinct values
stay distinct, so the recipient can still tell them apart. Expect a small false-positive
cost; it is far cheaper than a missed customer domain.

**Renaming paths is not optional.** Once file *contents* are rewritten, any
filename↔classname convention (PSR-4, and most autoloaders) is already broken until the
paths follow. Leaving paths alone does not keep the tree working — it keeps it broken.

## Notes on residual gitleaks findings

After scrubbing, a `gitleaks` re-scan typically still reports matches — these are
false positives, not live secrets: UUIDs inside SQL dumps, doc placeholders
(`YOUR_API_KEY`), the `REDACTED_*` markers this tool inserts, and library test
fixtures. Verify by inspection; the structured provider formats are already gone.
Treat any credential that was real in the original history as **rotated at source**.
