#!/usr/bin/env python3
"""Destroy all legible text in photographs of screens.

A phone photo of a monitor cannot be masked selectively: OCR cannot find the words, so
there is nothing to paint over, and its clean report means nothing. On one set a database
name plainly legible to a human read as garbage at every scale, page-segmentation mode
and inversion tried.

METHOD: downscale to a 16px long edge, then scale back up. Destructive by construction,
not by degree -- the information is gone at the downscale and no sharpening recovers it.
A Gaussian blur alone is NOT equivalent: it is a convolution, and heavy-but-finite blur
leaves large text readable. 64px was not enough either, and the failure was visible only
by eye: a hero headline stayed fully legible while OCR of that same blurred image
returned nonsense. Checked visually: 64px readable, 32px guessable, 24px smeared,
16px colour only.

There is no valid automated gate here. OCR is blind both to what the blur leaves and to
what it removes. Laplacian variance responds to the upscale's interpolation knots rather
than to characters. Confirm with contact sheets and human eyes.

Usage: blur_photos.py SRC_DIR DST_DIR [LONG_EDGE]
"""
import glob, os, sys
from PIL import Image, ImageFilter

EXT = ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp')


def is_photo(path):
    """Photograph, or synthetic screenshot?

    A screenshot is synthetic: large flat-colour runs, few distinct colours for its size.
    A photo of a screen carries sensor noise everywhere. That decides whether OCR can be
    trusted on the image at all.
    """
    im = Image.open(path).convert('RGB')
    px = im.width * im.height
    return bool(px) and len(im.getcolors(maxcolors=1000000) or []) / px > 0.05


def blur(src, dst, long_edge):
    im = Image.open(src).convert('RGB')
    w, h = im.size
    s = long_edge / max(w, h)
    small = im.resize((max(1, int(w * s)), max(1, int(h * s))), Image.LANCZOS)
    out = small.resize((w, h), Image.BILINEAR).filter(ImageFilter.GaussianBlur(2))
    os.makedirs(os.path.dirname(dst) or '.', exist_ok=True)
    if dst.lower().endswith('.webp'):
        out.save(dst, lossless=True, quality=100)
    elif dst.lower().endswith(('.jpg', '.jpeg')):
        out.save(dst, quality=100, subsampling=0)
    else:
        out.save(dst)


def main(src_dir, dst_dir, long_edge=16):
    files = [f for f in sorted(glob.glob(f'{src_dir}/**/*', recursive=True))
             if f.lower().endswith(EXT)]
    photos = [f for f in files if is_photo(f)]
    print(f'{len(photos)} photographs of {len(files)} images '
          f'({len(files) - len(photos)} native screenshots left alone)')
    for n, f in enumerate(photos, 1):
        blur(f, f.replace(src_dir, dst_dir), long_edge)
        if n % 20 == 0:
            print(f'  {n}/{len(photos)}...', flush=True)
    print(f'blurred to a {long_edge}px long edge -- REVIEW THE RESULT BY EYE')
    return 0


if __name__ == '__main__':
    if len(sys.argv) not in (3, 4):
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1].rstrip('/'), sys.argv[2].rstrip('/'),
                  int(sys.argv[3]) if len(sys.argv) == 4 else 16))
