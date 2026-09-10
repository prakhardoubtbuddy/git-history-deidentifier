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
   than contradictions: on one estate the great majority matched a separate internal
   record verbatim and the residue differed only by a leading group prefix — a formatting
   difference, not different objects. Chase the residue until you can say which it is.

Then treat it as what it is: `chmod 600`, out of version control, out of every published
directory. A recovered key is exactly as sensitive as the original.

**Watch for a second pseudonym layer.** Where source was scrubbed as well as catalogued,
names inside the delivered code may differ from the names in the catalogue — two
substitutions applied at different stages. Tracing a delivered item back to its origin
then needs both maps, and having only one produces a confident wrong answer.

## A second recipient, from the same corpus

Sooner or later a different recipient gets a different slice of the same data. Two
decisions arrive together, and the instinct is wrong on both.

### Strip the columns that describe how the corpus was assembled

Pseudonymising the identifiers is the visible half. The half that gets missed is a
structural column — `batch`, `lot`, `source`, `cohort`, whatever the pipeline called it —
that survives untouched because it holds no names. It does not need names. Counting rows
per distinct value tells the recipient how many items came from which acquisition, and
therefore how the corpus was built and roughly what it cost to build.

That happened here: the first spreadsheet sent to one recipient carried the internal batch
labels in two columns. Only a later file masked them to a constant, and by then the
information had gone out. Set those columns to a single value — the recipient's own name
works — and assert it:

```python
assert not any('batch-' in str(v) for r in rows for v in r.values())
```

The same applies to a group key built by concatenating that column onto something else.

### One pseudonym space, not one per recipient

Minting fresh codes per recipient feels safer. Measure what it actually buys before paying
for it.

**It buys less than it appears.** Both files carry the same measurements — sizes, counts,
first and last timestamps. Those pair rows exactly, whatever the identifiers say. Fresh
codes raise the effort from *obvious at a glance* to *a deliberate join*; they do not make
the slices unlinkable, and describing them as if they do is overselling.

**It costs accuracy on your side.** Every namespace is another key to hold, another
translation to get right, and another way to answer confidently and wrongly. Where source
was scrubbed as well as catalogued there are already two layers; a third is not free. On
this estate, having only one of two layers to hand had already produced a wrong answer the
same week the question came up.

So prefer one space, one key, one lookup — and write the residual risk down as a decision
that was taken rather than an oversight: **if two recipients compare files, matching codes
make any overlap obvious immediately.** That is the trade, and it should be made in the
open by whoever owns the commercial relationship, not silently by the person writing the
export script.

### Keep a ledger of who holds what

Slices of one corpus overlap, and pseudonymisation makes the overlap invisible. Two
recipients can hold the same item under the same code without anyone noticing, because
each delivery was correct in isolation and nothing joins them.

The moment you cannot answer *"who already has this item, and in what form?"* you cannot
answer the questions that follow it — whether anything was promised exclusively, whether a
withdrawal is even possible, what a given recipient would see if they compared notes with
another. Those questions arrive from the commercial side, not the technical one, and they
arrive late.

So maintain one record, updated whenever anything ships, that says per recipient: what they
received, in what form (metadata, or the underlying artifact), and when. Derive it from the
delivery artifacts rather than from memory — the counts drift otherwise, and a slice that
was built but never sent looks identical to one that shipped.

Building that record for the first time is also the cheapest audit available. On this estate
it immediately surfaced a completed package that had been sitting unsent for a month, and a
supplier appearing twice under two submissions that were being added together as though they
were one.
