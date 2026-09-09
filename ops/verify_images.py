#!/usr/bin/env python3
"""Independent OCR gate over masked images. Deliberately shares no code with the masker.

A masker that checks its own work agrees with itself. One reported 0 images with readable
text while this found 101 -- because the masker detected and verified at native
resolution, and text too small for that pass was neither painted nor flagged.

Reads each file FROM DISK (a lossy re-encode on save can resurrect painted-over text),
OCRs at 1x and 2x, and matches identifiers separator-insensitively, because 'First Last'
must match 'first_last'.

Photographs are reported but NOT vouched for: OCR could not read them before masking, so
a clean result on them afterwards is not evidence. Review those by eye.

Usage: verify_images.py MASKED_DIR VALUES_JSON
"""
import glob, json, os, re, sys
from PIL import Image
import pytesseract

EXT = ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp')


def norm(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())


def is_photo(im):
    px = im.width * im.height
    return bool(px) and len(im.getcolors(maxcolors=1000000) or []) / px > 0.05


def ocr(im):
    big = im.resize((im.width * 2, im.height * 2), Image.LANCZOS)
    return (pytesseract.image_to_string(im).strip() + '\n' +
            pytesseract.image_to_string(big).strip()).strip()


def main(masked_dir, values_json):
    raw = json.load(open(values_json))
    values = list(raw.keys()) if isinstance(raw, dict) else raw
    needles = sorted({norm(v) for v in values if len(norm(v)) >= 5})

    with_text, ident, photos = [], [], []
    files = [f for f in sorted(glob.glob(f'{masked_dir}/**/*', recursive=True))
             if f.lower().endswith(EXT)]
    for f in files:
        im = Image.open(f).convert('RGB')
        if is_photo(im):
            photos.append(f)
            continue
        t = ocr(im)
        if len(t) > 2:
            with_text.append((f, len(t), t[:70].replace('\n', ' ')))
        hit = sorted({n for n in needles if n in norm(t)})
        if hit:
            ident.append((f, hit))

    print(f'=== {len(files) - len(photos)} native screenshots -- OCR gate ===')
    print(f'   with any readable text : {len(with_text)}')
    print(f'   with an identifier     : {len(ident)}')
    for f, n, s in with_text[:20]:
        print(f'      {os.path.basename(f)[:38]:40} {n:4} chars: {s!r}')
    for f, h in ident:
        print(f'      *** {os.path.basename(f)[:38]}: {h}')
    print(f'\n=== {len(photos)} photographs -- no automated gate is valid here ===')
    print('   review contact sheets by eye; OCR cannot read these either way')
    return 1 if ident else 0


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1].rstrip('/'), sys.argv[2]))
