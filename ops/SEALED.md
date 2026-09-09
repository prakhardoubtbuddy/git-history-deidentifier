# De-identifying a sealed or signed artifact

An evaluation bundle that carries an integrity digest is not an ordinary file. Removing a
name from it breaks two things that are easy to conflate, and only one of them is the
digest.

## Removing a field invalidates the seal — silently, until the recipient checks

The digest is computed over the whole payload with the integrity block excluded. Drop a
single identifying field and it no longer recomputes. In one batch, **all 128
de-identified bundles failed their own integrity check** — the first thing the recipient
runs, and the one step guaranteed to be run.

So a de-identification pass over sealed artifacts has to **re-seal**, and say so:

```python
bundle["integrity"] = {
    "algo": "sha256",
    "canonical": "json sort_keys compact ascii, over payload excluding this block",
    "digest": recompute(bundle),
    "note": "... RE-SEALED after removing identifying fields; the result is unchanged "
            "and re-derives from the evidence embedded here.",
}
```

## Re-sealing is not enough: prove the RESULT did not move

A recomputed digest only says the file is internally consistent — it would happily certify
a bundle whose score had changed. The claim that matters is that de-identification removed
a label and nothing else. Check it directly: re-derive the result from each bundle's own
embedded evidence and compare.

Two traps, both hit here:

- **The re-derivation harness lied first.** The grader reads a second input file as a
  *sibling* of the first. Writing only the first to a temp file made every re-derivation
  return `None` — which printed as "the result moved on all 128 bundles" and looked like a
  catastrophic finding rather than a bug in the check. Reconstruct the whole input
  directory, not the one file you were thinking about.
- **A field can be identifying in one estate and absent in another.** One vendor's files
  carried the identifier in every record; another's carried none, but had a second field
  the first lacked. Strip the union, or the two packages end up structurally different —
  and that difference is itself a signal about which is which.

## Withholding the tool does not protect its thresholds

Refusing to ship the scoring script feels like it keeps the method internal. It does not,
if the output pairs each score with the band it fell into. With enough records the
boundaries are pinned between adjacent observed scores — here, to a fraction of a point,
on round numbers anyone would then guess exactly. Component maxima shipped alongside give
away the weighting just as directly.

If thresholds are genuinely internal, the question is not *"do we send the script?"* but
*"does the recipient need our scoring at all?"* Often they asked for the raw measurements
so they could run their own — in which case shipping only those removes the problem
instead of managing it.

## Name the package by an intrinsic property, not by its subject

`bundles-<count>-repos.tar.gz` can be renamed per recipient without touching its contents,
and the count is a fingerprint that survives renaming. A filename is a leak surface like
any other: identifiers hide in directory names and archive names long after every field
inside has been cleaned.
