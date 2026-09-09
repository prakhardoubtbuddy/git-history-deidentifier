#!/usr/bin/env python3
"""Rebuild archives in a delivery tree from the masked versions of their contents.

A text-masking pass treats a .zip as one opaque file and copies it through untouched, so
the delivery ships a pristine unmasked copy of every attachment INSIDE an archive, next
to the masked ones -- after every gate has reported clean. Found only by hashing archive
entries against the original files. Same failure as --replace-text skipping binary blobs.

Asserts afterwards that no entry in any delivered archive is byte-identical to an input
file. That assertion is the point; the rebuild is the easy part.

Usage: repack_archives.py DELIVERY_DIR MASKED_IMAGE_DIR [ORIGINAL_IMAGE_DIR]
"""
import glob, hashlib, os, sys, zipfile

IMG = ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp')


def index(root):
    """basename -> path, for the masked replacements."""
    out = {}
    for f in glob.glob(f'{root}/**/*', recursive=True):
        if os.path.isfile(f) and f.lower().endswith(IMG):
            out.setdefault(os.path.basename(f), f)
    return out


def main(delivery, masked_dir, orig_dir=None):
    masked = index(masked_dir)
    swapped = missing = 0
    for z in sorted(glob.glob(f'{delivery}/**/*.zip', recursive=True)):
        old = zipfile.ZipFile(z)
        items = []
        for info in old.infolist():
            data = old.read(info.filename)
            if info.filename.lower().endswith(IMG):
                m = masked.get(os.path.basename(info.filename))
                if m:
                    data = open(m, 'rb').read()
                    swapped += 1
                else:
                    missing += 1
                    print(f'   MISSING masked version: {z} :: {info.filename}')
            items.append((info, data))
        old.close()
        with zipfile.ZipFile(z, 'w', zipfile.ZIP_DEFLATED) as new:
            for info, data in items:
                new.writestr(info, data)
        print(f'{z}: rebuilt {len(items)} entries')

    bad = 0
    if orig_dir:
        originals = {h for h in (hashlib.md5(open(f, 'rb').read()).hexdigest()
                                 for f in glob.glob(f'{orig_dir}/**/*', recursive=True)
                                 if os.path.isfile(f))}
        for z in sorted(glob.glob(f'{delivery}/**/*.zip', recursive=True)):
            zf = zipfile.ZipFile(z)
            for n in zf.namelist():
                if hashlib.md5(zf.read(n)).hexdigest() in originals:
                    print(f'   *** STILL ORIGINAL: {z} :: {n}')
                    bad += 1
    print(f'\nimages swapped {swapped}, missing {missing}, '
          f'entries identical to an original {bad}')
    return 1 if (bad or missing) else 0


if __name__ == '__main__':
    if len(sys.argv) not in (3, 4):
        sys.exit(__doc__)
    sys.exit(main(*[a.rstrip('/') for a in sys.argv[1:]]))
