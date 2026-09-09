#!/usr/bin/env python3
"""Second pass on the film pages: mask a full-width strip at the top of every tile row.

The first pass assumed one 5x7 layout and masked the top-left and top-right CORNER of
each tile. Two of the six pages are 6x5, so those boxes landed in the wrong places and
the name stayed on the page.

Rather than detect columns per file, mask a full-width band at the top of each tile ROW.
The text always sits at the top of a tile, whatever the column count -- so row geometry
alone is sufficient, and the number of columns stops mattering.

Cost: a thin band of anatomy at the top of each row on the contact sheet. The
full-resolution diagnostic slices are untouched, so nothing diagnostic is lost.
"""
import glob, os
import numpy as np
import pydicom

BAND = 100          # text occupies ~95px at the top of a tile
films = [p for p in sorted(glob.glob(f"{os.environ.get('DICOM_DST','work/deid')}/**/*.dcm", recursive=True))
         if 'Electronic film' in str(pydicom.dcmread(p, stop_before_pixels=True)
                                    .get('SeriesDescription', ''))]

for p in films:
    ds = pydicom.dcmread(p)
    a = np.asarray(ds.pixel_array)
    work = a[0] if a.ndim > 2 and a.shape[0] < 5 else a
    h, w = work.shape
    fill = int(np.percentile(work, 1))

    # tile rows are separated by thin bright dividers spanning the full width
    rowmean = work.mean(axis=1)
    thr = np.percentile(rowmean, 99)
    cand = np.where(rowmean > thr)[0]
    seps, s, prev = [], None, None
    for x in cand:
        if s is None: s = x
        elif x - prev > 40: seps.append((s + prev) // 2); s = x
        prev = x
    if s is not None: seps.append((s + prev) // 2)
    # keep only the regularly spaced ones - the real grid
    seps = [x for x in seps if 200 < x < h - 200]
    starts = [162] + [x + 1 for x in seps]        # 162 = below the banner

    work[:162, :] = fill                          # banner
    n = 1
    for y0 in starts:
        work[y0:min(h, y0 + BAND), :] = fill
        n += 1
    if a.ndim > 2 and a.shape[0] < 5: a[0] = work
    else: a = work
    ds.PixelData = a.tobytes()
    ds['PixelData'].VR = 'OW' if a.dtype.itemsize == 2 else 'OB'
    ds.file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
    ds.BurnedInAnnotation = 'NO'
    ds.save_as(p, enforce_file_format=True)
    print(f"  {p.split('/')[2]}/{p.split('/')[-1]}  {w}x{h}  rows detected={len(seps)}  bands masked={n}")
print(f"\n{len(films)} film pages re-masked by row")
