#!/usr/bin/env python3
"""Paint over every text region in native screenshots.

Masks ALL text rather than classifying which words are sensitive: deciding "this word is
safe" hundreds of times is a judgement that will be wrong somewhere, and these images are
worth keeping for their layout, not their words.

Two failures this exists to avoid, both of which produced a confident clean report:

  * SAVE LOSSLESS AND VERIFY THE FILE. Saving a .webp re-encodes lossily and brings back
    faint edges of text just painted over. Checking the in-memory image passes; the file
    on disk still reads.
  * DETECT ABOVE NATIVE RESOLUTION. Boxes from image_to_data at 1x plus a stop-condition
    from image_to_string at 1x share a blind spot: text too small for either is neither
    painted nor flagged.

Not for photographs of screens -- see blur_photos.py and the README.

Usage: mask_image_text.py SRC_DIR DST_DIR
"""
import glob, os, sys
import pytesseract
from PIL import Image, ImageDraw

MAX_PASSES = 8
SCALE = 2
EXT = ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp')


def boxes(im):
    """Word boxes in NATIVE coords, unioned across an upscale and sparse-text mode."""
    out = []
    big = im.resize((im.width * SCALE, im.height * SCALE), Image.LANCZOS)
    for img, sc, cfg in ((im, 1, ''), (big, SCALE, ''), (big, SCALE, '--psm 11')):
        try:
            d = pytesseract.image_to_data(img, config=cfg,
                                          output_type=pytesseract.Output.DICT)
        except Exception:
            continue
        for i in range(len(d['text'])):
            if not d['text'][i].strip():
                continue
            w, h = d['width'][i], d['height'][i]
            if w > 0 and h > 0:
                out.append((d['left'][i] // sc, d['top'][i] // sc, w // sc, h // sc))
    return out


def readable(im):
    big = im.resize((im.width * SCALE, im.height * SCALE), Image.LANCZOS)
    return (pytesseract.image_to_string(im).strip() + '\n' +
            pytesseract.image_to_string(big).strip()).strip()


def save(im, dst):
    os.makedirs(os.path.dirname(dst) or '.', exist_ok=True)
    if dst.lower().endswith('.webp'):
        im.save(dst, lossless=True, quality=100)
    elif dst.lower().endswith(('.jpg', '.jpeg')):
        im.save(dst, quality=100, subsampling=0)
    else:
        im.save(dst)


def mask_image(src, dst):
    im = Image.open(src).convert('RGB')
    painted = 0
    for _ in range(MAX_PASSES):
        bs = boxes(im)
        if not bs:
            break
        draw = ImageDraw.Draw(im)
        for x, y, w, h in bs:
            sx, sy = max(0, x - 3), min(im.height - 1, max(0, y + h // 2))
            try:
                bg = im.getpixel((sx, sy))          # match the word's own background
            except Exception:
                bg = (255, 255, 255)
            draw.rectangle([x - 3, y - 3, x + w + 3, y + h + 3], fill=bg)
        painted += len(bs)
        if len(readable(im)) < 3:
            break
    save(im, dst)
    # the only verdict that counts: what a recipient opening the file would see
    return painted, len(readable(Image.open(dst).convert('RGB')))


def main(src_dir, dst_dir):
    files = [f for f in sorted(glob.glob(f'{src_dir}/**/*', recursive=True))
             if f.lower().endswith(EXT)]
    print(f'{len(files)} images')
    total, stubborn = 0, []
    for n, f in enumerate(files, 1):
        try:
            painted, left = mask_image(f, f.replace(src_dir, dst_dir))
        except Exception as e:
            print(f'  ERROR {f}: {e}')
            continue
        total += painted
        if left > 2:
            stubborn.append((f, left))
        if n % 20 == 0:
            print(f'  {n}/{len(files)}...', flush=True)
    print(f'\nwords painted: {total:,}')
    print(f'images with text still readable ON DISK: {len(stubborn)}')
    for f, l in stubborn[:40]:
        print(f'   {f}  {l} chars')
    return 1 if stubborn else 0


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1].rstrip('/'), sys.argv[2].rstrip('/')))
