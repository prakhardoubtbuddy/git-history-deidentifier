# ops — de-identifying exported operational data

Chat, board and workstream exports (Teams, Trello, freelancer platforms): text files plus
the images people pasted into conversations.

```bash
./mask_text.py       SRC DST MAP.json    # names/orgs -> pseudonyms, contacts by pattern
./mask_image_text.py SRC DST             # paint over every word in native screenshots
./blur_photos.py     SRC DST             # destroy text in photographs of screens
./repack_archives.py DST SRC_IMAGES      # rebuild archives from the masked images
./verify_images.py   SRC DST MAP.json    # independent OCR gate
./scan_output.py     DST values.json     # search the OUTPUT for values from the INPUT
```

## The one check that works

Search the finished output for strings known to be in the input, and look at the images.
Nothing else here has ever caught anything. Every gate that asked *"did my tool report
success?"* passed while the data was still leaking.

## Three ways a verification confirms its own blind spot

All three happened in a single engagement, each looking like proof.

**1. Verify the file, not the object in memory.** The masker OCR'd the in-memory image,
read nothing, and saved. `Image.save()` on a `.webp` re-encodes **lossily**, and the
compression brought back faint edges of the text it had just painted over. It had
verified an image that never reached the disk. Reported 0 bad; an independent re-OCR of
the files found 31. Save lossless (`lossless=True`, or `quality=100, subsampling=0` for
JPEG) and re-open the written file to check it.

**2. Detection and verification must not share a resolution.** Boxes came from
`image_to_data` at native size; the stop-condition was `image_to_string` at native size.
Text too small for one is invisible to the other, so it was neither painted nor flagged —
a silent, self-consistent pass. Reported 0; a 2x-upscale re-OCR found 101 images with
readable text. Detect on an upscale, union in `--psm 11`, verify on an upscale too.

**3. Separators vary; word boundaries must not.** Replacement matched exact literals with
single spaces. Chat exports write **two** spaces around an @mention, so `First  Last`
survived — as did `First-Last`, `FirstLast`, the same name as a domain, and an email
flattened into a URL slug. 24 original values survived a pass already reported clean,
because the check matched literally as well and agreed with it. Build each value into
`run[^A-Za-z0-9]{0,3}run`, anchored both ends:

```python
body = r'[^A-Za-z0-9]{0,3}'.join(re.escape(p) for p in re.split(r'[^A-Za-z0-9]+', value) if p)
rx = re.compile(r'(?<![A-Za-z0-9])' + body + r'(?![A-Za-z0-9])', re.IGNORECASE)
```

Do **not** instead strip punctuation from whole documents and substring-match: adjacent
words fuse, and `"and resolve"` then contains the name `Andres`.

## OCR cannot certify a photograph of a screen

A phone photo of a monitor is not a screenshot. On one set, 42% were photos, and a
database name plainly legible to a human read as `FADIC` / `NADIE` / `ADIGE` at every
scale, page-segmentation mode and inversion tried. A clean OCR result on such an image is
not evidence of anything — and neither is a clean result *after* masking it.

Separate the two classes before choosing a method; they need different ones:

```python
uniq_ratio = len(im.getcolors(maxcolors=1_000_000) or []) / (im.width * im.height)
is_photo = uniq_ratio > 0.05        # synthetic screenshots have large flat-colour runs
```

Native screenshots can be masked selectively and verified by OCR. Photographs cannot be
verified by machine at all, so the only defensible options are to drop them, blur them
destructively, or have a person look at every one.

## Blur must destroy, not convolve

Reduce the long edge to **16px** and scale back up. The information is gone at the
downscale; no sharpening recovers it.

A Gaussian blur alone is not equivalent — it is a convolution, and heavy-but-finite blur
leaves large text readable. Even the downscale has to be taken far enough: at a 64px long
edge a hero headline was still fully legible while OCR of that same blurred image
returned `entities caine a`. So OCR is blind **both** to what the blur leaves and to what
it removes, and cannot gate either end. Set the level by construction and confirm it by
eye on contact sheets: 64px readable, 32px guessable, 24px smeared, 16px colour only.

⛔ **Laplacian variance is not a text gate.** After an upscale it responds to the
interpolation knots, not to characters, and reports a healthy-looking number for an image
containing nothing at all.

## An archive is a container, not a file

The text pass copied the attachment `.zip`s through untouched, so the delivery carried a
pristine, unmasked copy of every image *inside a zip*, next to the masked ones. Every
gate had reported clean. Caught only by hashing each zip entry against the originals.

Rebuild archives from the masked files and assert that no entry is byte-identical to an
input file. Same failure as `--replace-text` skipping binary blobs: something treated the
container as one opaque object and never looked inside.

## Mask to a copy, never in place

The first image pass overwrote its inputs, so a bad pass was unrecoverable and the second
pass compounded on the first. Keep the originals read-only and write elsewhere.
