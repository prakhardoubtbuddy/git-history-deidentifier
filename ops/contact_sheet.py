#!/usr/bin/env python3
"""Contact sheets of masked images, for the human review that machines cannot replace.

Only photographs of screens need this: OCR cannot certify them, so a person has to look.
Including the native screenshots as well would only dilute attention on the ones that
actually need it.

Usage: contact_sheet.py IMAGE_DIR OUT_DIR
"""
import glob, os, sys
from PIL import Image, ImageDraw, ImageFont

COLS, ROWS, TILE = 4, 3, 480
EXT = ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp')


def is_photo(path):
    im = Image.open(path).convert('RGB')
    px = im.width * im.height
    return bool(px) and len(im.getcolors(maxcolors=1000000) or []) / px > 0.05


def main(img_dir, out_dir):
    photos = [f for f in sorted(glob.glob(f'{img_dir}/**/*', recursive=True))
              if f.lower().endswith(EXT) and is_photo(f)]
    os.makedirs(out_dir, exist_ok=True)
    try:
        font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 15)
    except Exception:
        font = ImageFont.load_default()

    per = COLS * ROWS
    for page, start in enumerate(range(0, len(photos), per), 1):
        chunk = photos[start:start + per]
        sheet = Image.new('RGB', (COLS * TILE, ROWS * (TILE + 26)), (250, 250, 250))
        d = ImageDraw.Draw(sheet)
        for i, src in enumerate(chunk):
            im = Image.open(src).convert('RGB')
            im.thumbnail((TILE - 8, TILE - 8), Image.LANCZOS)
            cx, cy = (i % COLS) * TILE, (i // COLS) * (TILE + 26)
            sheet.paste(im, (cx + 4, cy + 22))
            d.text((cx + 5, cy + 4), f'{start + i + 1:02d}  {os.path.basename(src)[:34]}',
                   fill=(0, 0, 0), font=font)
            d.rectangle([cx + 2, cy + 20, cx + TILE - 2, cy + TILE + 22], outline=(200, 200, 200))
        sheet.save(f'{out_dir}/sheet-{page:02d}.png')
        print(f'  wrote {out_dir}/sheet-{page:02d}.png')
    print(f'{len(photos)} photographs for review')
    return 0


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1].rstrip('/'), sys.argv[2].rstrip('/')))
