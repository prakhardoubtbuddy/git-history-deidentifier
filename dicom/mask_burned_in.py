#!/usr/bin/env python3
"""Paint over burned-in identifiers in the rendered images.

Only 7 of the 4,858 files need this. The other 4,851 are diagnostic slices with no
text in them, and the six 3D/scout overlays were checked by eye and carry only scan
geometry.

WHY BY EYE AND NOT BY DETECTOR: a statistical text detector scored two of these film
pages "clean" when each carries the patient's name 36 times. The DICOM
BurnedInAnnotation tag is absent on all 4,858 files, so the format gives no warning
either. Looking at the picture was the only thing that worked.

FILM PAGES are a 5x7 contact sheet. The name is in a banner across the top AND in the
top-left corner of every one of the 35 tiles, with the institution top-right. Masking
the banner alone leaves 35 copies.

DOSE REPORT carries no name -- only Study ID and the exam timestamp.
"""
import glob, os, json, os
import numpy as np
import pydicom

DEID = os.environ.get('DICOM_DST','work/deid')
SC = {'1.2.840.10008.5.1.4.1.1.7', '1.2.840.10008.5.1.4.1.1.7.4'}
report = []

for p in sorted(glob.glob(f'{DEID}/**/*.dcm', recursive=True)):
    h = pydicom.dcmread(p, stop_before_pixels=True)
    if str(h.get('SOPClassUID', '')) not in SC:
        continue
    desc = str(h.get('SeriesDescription', ''))
    ds = pydicom.dcmread(p)
    a = np.asarray(ds.pixel_array)
    orig_shape = a.shape
    work = a[0] if a.ndim > 2 and a.shape[0] < 5 else a
    if work.ndim > 2:
        report.append((p, desc, 'SKIPPED: unexpected shape', 0)); continue
    hgt, wid = work.shape
    fill = int(np.percentile(work, 1))
    boxes = 0

    if 'Electronic film' in desc and wid > 3000:
        TOP, rows, cols = 162, 7, 5
        th = (hgt - TOP - 11) // rows
        tw = wid // cols
        work[:TOP, :] = fill; boxes += 1                       # banner
        for r in range(rows):
            for c in range(cols):
                y0, x0 = TOP + r * th, c * tw
                work[y0:y0+95,  x0:x0+300]           = fill    # name / ID / date
                work[y0:y0+70,  x0+tw-120:x0+tw]     = fill    # institution / vendor
                boxes += 2
    elif 'Dose' in desc:
        work[33:92, 335:wid] = fill; boxes += 1                # Study ID + timestamp values
    else:
        report.append((p, desc, 'no burned-in identifiers (checked visually)', 0)); continue

    if a.ndim > 2 and a.shape[0] < 5: a[0] = work
    else: a = work
    ds.PixelData = a.astype(a.dtype).tobytes()
    ds['PixelData'].VR = 'OW' if a.dtype.itemsize == 2 else 'OB'
    # the pixels are no longer the compressed original
    ds.file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
    ds.is_implicit_VR = False; ds.is_little_endian = True
    ds.BurnedInAnnotation = 'NO'
    ds.save_as(p, enforce_file_format=True)
    report.append((p, desc, f'masked {boxes} regions', boxes))

print(f"{'file':<52}{'series':<34}action")
for p, d, act, n in report:
    print(f"  {os.path.relpath(p, DEID)[:50]:<52}{d[:32]:<34}{act}")
tot = sum(n for *_, n in report)
print(f"\n{sum(1 for *_ ,n in report if n)} images masked, {tot} regions painted")
