# DICOM de-identification

Removing patient identity from medical imaging studies. Same discipline as the git and
audio tooling; the hiding places are different.

| step | script |
|---|---|
| 1. de-identify headers, UIDs, dates | `deid_dicom.py` |
| 2. mask burned-in text | `mask_burned_in.py`, then `mask_film_rows.py` |
| 3. **verify, on the output** | `verify_deid.py` |

## Five places identity hides, in increasing order of how easy it is to miss

### 1. The filenames

Exports routinely name the archive after the patient:
`<hospitalID>_CT_<FULLNAME><age><sex>.zip`. Full name, ID, age and sex, readable
without opening a file.

### 2. The headers

Name, ID, date of birth, sex, institution name AND street address, accession number,
study ID, exact date and time, scanner serial, station name. The bulk of it, and the
tractable part.

### 3. The patient ID is inside the UIDs

    StudyInstanceUID = 1.2.826.1.3680043.9.5282.150415.<patientID>.<accession>

Blanking `PatientID` leaves the same facts one level down, in a field that looks like
an opaque number. **Regenerate UIDs; never merely blank the ID.** Use one consistent
old→new map: the same old UID must always yield the same new one, or the slices stop
belonging to the same series.

### 4. UIDs nested inside sequences

`ReferencedImageSequence`, `SourceImageSequence` and a dose report's `ContentSequence`
carry their own UIDs. Remapping only top-level tags leaves the originals in place —
and **breaks every reference**, because the thing pointed at changed and the pointer
did not. That failure surfaces for whoever opens the study, not for you.

Apply the map **recursively**. `verify_deid.py` check 2 exists for precisely this.

### 5. `OriginalAttributesSequence`

The PACS's own record of a previous edit. It stores **the values as they were before
that edit**, plus the system that made it. A de-identifier that ignores it leaves a
tidy copy of what you just removed. Delete it.

Also: dates baked into free-text labels, e.g. `Electronic film_20250930210702`.

## Burned-in pixel text

Rendered "electronic film" contact sheets print the patient's name into the image —
**once in a banner and again in the top corner of every tile.** On one 5×7 sheet that
is 36 copies. Masking the banner removes one of them.

Three things that make this harder than it sounds:

- **`BurnedInAnnotation` cannot be relied on.** It was ABSENT on all 4,858 files of a
  set where six images carried the name 36 times each. The format gives no warning.
- **A statistical text detector is not sufficient.** One scored two of those six pages
  "clean". Edge-density thresholds do not separate printed text from anatomy reliably.
  Render the image and look at it.
- **Tile layouts vary between pages of the same study** (5×7 and 6×5 were both
  present). Corner boxes computed from an assumed grid land in the wrong place.
  `mask_film_rows.py` masks a full-width band at the top of each *detected* row, which
  works whatever the column count, at the cost of a thin band of anatomy on a contact
  sheet whose full-resolution slices are untouched.

## Dates

Shift by one random offset per patient rather than blanking. Intervals within a study
stay correct — a delayed-phase series remains the right number of minutes after the
plain one — while the real calendar date is gone. Blanking destroys the temporal
relationship that makes a study usable.

## Configuration

`deid_dicom.py` reads site-specific strings (scanner serials, station names, PACS
titles) from `$DICOM_DEVICE_STRINGS`, default `/etc/deid/device-strings.txt`.

**That file is not in this repo and must not be.** It names a specific institution's
equipment. The tag-level rules run without it; the list catches the same values where
they appear in free text or a nested sequence.

## What to keep

Patient sex and age, body part, scanner make and model, acquisition parameters, and
the pixel data. These carry no identity, and removing them costs the clinical value
that made the study worth sharing.

## Limits

Head and neck imaging can be volume-rendered into a recognisable face. No header
change prevents that; it requires altering the anatomy, which may destroy the clinical
value. Abdominal and limb studies are unaffected.

Re-identification by anyone holding the original study cannot be prevented by any of
this.
