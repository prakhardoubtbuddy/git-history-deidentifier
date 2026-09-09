#!/usr/bin/env python3
"""Verify a de-identified DICOM set. Four checks, all on the OUTPUT.

Every mistake this pipeline made was found by one of these, and none of them by
reading the code or trusting a summary line.

  1. KNOWN-STRING SEARCH. Search every output file for each string you know was in
     the input -- names, IDs, dates of birth, accession numbers, the institution,
     device serials. This is the check that found the patient ID surviving inside
     StudyInstanceUID after the ID field had been blanked.

  2. REFERENCE INTEGRITY. Count dangling ReferencedSOPInstanceUIDs in the output and
     compare with the SAME count on the input. They must MATCH. A set can legitimately
     reference images outside itself, so a non-zero count is not a fault -- a count
     that CHANGED means the UID remap broke the links. Remapping only top-level UIDs
     does exactly that, silently.

  3. PRIVATE TAGS. Odd-group elements are undocumented and vendor-specific. Any
     remaining is a place nobody has looked.

  4. OCR. Render every Secondary Capture image and read it. The DICOM
     BurnedInAnnotation tag cannot be relied on -- it was ABSENT on all 4,858 files of
     a set where six images had the patient's name printed 36 times each.

     OCR is corroboration, not proof: on that same set it also read nothing from one
     film page that plainly carried text. Run it against the ORIGINALS too. If OCR
     cannot read the name off the input, its silence on the output means nothing.

Usage: verify_deid.py ORIGINAL_DIR DEIDENTIFIED_DIR [strings.txt]
"""
import glob, os, sys, collections
import pydicom

SC = {'1.2.840.10008.5.1.4.1.1.7', '1.2.840.10008.5.1.4.1.1.7.4'}

def refs_and_sops(root):
    sop, refs = set(), []
    for f in sorted(glob.glob(f'{root}/**/*.dcm', recursive=True)):
        ds = pydicom.dcmread(f, stop_before_pixels=True)
        if 'SOPInstanceUID' in ds:
            sop.add(str(ds.SOPInstanceUID))
        def walk(d):
            for el in d:
                if el.VR == 'SQ':
                    for it in (el.value or []): walk(it)
                elif el.keyword == 'ReferencedSOPInstanceUID' and el.value:
                    refs.append(str(el.value))
        walk(ds)
    return sop, refs

def ocr_hits(root, secrets):
    try:
        import numpy as np, pytesseract
        from PIL import Image
    except ImportError:
        return None
    out = {}
    for f in sorted(glob.glob(f'{root}/**/*.dcm', recursive=True)):
        h = pydicom.dcmread(f, stop_before_pixels=True)
        if str(h.get('SOPClassUID', '')) not in SC:
            continue
        try:
            a = np.asarray(pydicom.dcmread(f).pixel_array).astype(np.float32)
        except Exception:
            out[f] = ['<pixels unreadable>']; continue
        if a.ndim > 2: a = a[0]
        lo, hi = np.percentile(a, [1, 99])
        im = Image.fromarray(((np.clip((a - lo) / max(1e-6, hi - lo), 0, 1)) * 255).astype('uint8'))
        if im.width > 2500: im = im.resize((im.width // 2, im.height // 2), Image.LANCZOS)
        t = pytesseract.image_to_string(im).upper()
        hit = [s for s in secrets if s.upper() in t]
        if hit: out[f] = hit
    return out

def main(orig, deid, strfile=None):
    secrets = []
    if strfile and os.path.exists(strfile):
        secrets = [l.strip() for l in open(strfile) if l.strip() and not l.startswith('#')]
    if not secrets:
        print('NOTE: no strings file given. Check 1 and check 4 can only be as good as\n'
              '      the list of things you know were in the input.\n')

    print('CHECK 1 - known identifying strings in the output')
    hits = collections.Counter(); priv = 0; n = 0
    for f in sorted(glob.glob(f'{deid}/**/*.dcm', recursive=True)):
        ds = pydicom.dcmread(f, stop_before_pixels=True); n += 1
        blob = (str(ds) + str(getattr(ds, 'file_meta', ''))).upper()
        for s in secrets:
            if s.upper() in blob: hits[s] += 1
        if any(e.tag.group % 2 == 1 for e in ds): priv += 1
    print(f'   files scanned : {n}')
    print(f'   strings found : {dict(hits) if hits else "NONE"}')

    print('\nCHECK 2 - reference integrity (must MATCH the original)')
    so, ro = refs_and_sops(orig); sd, rd = refs_and_sops(deid)
    do = sum(1 for r in ro if r not in so); dd = sum(1 for r in rd if r not in sd)
    print(f'   original      : {len(ro):,} references, {do:,} dangling')
    print(f'   de-identified : {len(rd):,} references, {dd:,} dangling')
    print(f'   verdict       : {"OK - unchanged" if (do, len(ro)) == (dd, len(rd)) else "*** CHANGED - the UID remap broke links"}')

    print('\nCHECK 3 - private tags')
    print(f'   files with odd-group elements: {priv}')

    print('\nCHECK 4 - OCR over rendered images')
    oo = ocr_hits(orig, secrets); od = ocr_hits(deid, secrets)
    if oo is None:
        print('   skipped (needs pytesseract, pillow, numpy)')
    else:
        print(f'   originals showing an identifier    : {len(oo)}  <- if 0, OCR proves nothing below')
        print(f'   de-identified showing an identifier: {len(od)}')
        for f, h in list(od.items())[:5]: print(f'      *** {f}: {h}')

    ok = not hits and priv == 0 and (do, len(ro)) == (dd, len(rd)) and not (od or {})
    print(f'\n=== {"PASS" if ok else "FAIL - see above"} ===')
    return 0 if ok else 1

if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    sys.exit(main(*sys.argv[1:4]))
