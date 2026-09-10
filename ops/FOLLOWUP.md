# Sending a follow-up to a recipient who already holds a de-identified file

The second delivery is more dangerous than the first. The first was built deliberately;
the second gets built from whatever is nearest to hand, which is your working copy.

## Read the schema off what was SENT, not off the file it was generated from

They differ, and the internal one looks authoritative — same name, same shape, richer
columns, sitting in the folder where the work happened.

Concretely, on one estate the internal working file and the delivered file diverged in
three ways that all mattered:

| | internal working file | what the recipient holds |
|---|---|---|
| columns | 37 | **36** |
| `org` / `project_name` | the procurement batch | a single constant |
| group key | `<batch>__<project>` | bare `<project>` |

The extra column was a commercial field. The batch values revealed **how many items came
from which purchase** — a fact about how the estate was assembled, which no recipient of
a sample is owed and which cannot be withdrawn once sent. And the mismatched keys would
not have joined to the file they already had, so the delivery would have been wrong on
its own terms as well as leaky.

None of that is visible from inside the working directory. Diff against the delivered
artifact — the actual file, not the script that made it:

```python
schema = next(csv.reader(open(DELIVERED_FILE)))   # authoritative column order
assert 'commercial_field' not in schema
...
rows = [{c: r.get(c, '') for c in schema} for r in new_rows]
assert list(rows[0]) == schema
```

Reconcile the two halves as well: `new + already_sent == the original set`, with zero
overlap and every member present exactly once. Sum an invariant metric across both and
check it equals the original total — that catches a subtly different source file, which
a row count does not.

## Reconstructing a pseudonym map you no longer have

The map is the one artifact most likely to be missing later: it is the thing you were
careful not to commit, so it lives in a scratch directory and disappears.

It is often recoverable, because the masked and unmasked exports were written from the
same rows in the same order. Pair them positionally — but a positional join is only
worth as much as its proof, and without one it is a guess that looks like a key:

1. **Verify the alignment** on fields the masking could not have touched — sizes, counts,
   timestamps. Every row must match, not most.
2. **Cross-validate against a subset whose true values are independently known** — a
   batch already delivered, whose own manifest survives. Agreement on every one of those
   is the evidence that the whole reconstruction is sound.
3. **Sanity-check against a second source** if one exists. Expect naming variants rather
   than contradictions: on one estate 178 of 246 matched a separate internal record
   verbatim and the remaining 68 differed only by a group prefix — a formatting
   difference, not different objects. Chase the residue until you can say which it is.

Then treat it as what it is: `chmod 600`, out of version control, out of every published
directory. A recovered key is exactly as sensitive as the original.

**Watch for a second pseudonym layer.** Where source was scrubbed as well as catalogued,
names inside the delivered code may differ from the names in the catalogue — two
substitutions applied at different stages. Tracing a delivered item back to its origin
then needs both maps, and having only one produces a confident wrong answer.
