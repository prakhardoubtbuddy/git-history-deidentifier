#!/usr/bin/env python3
"""De-identify the CT studies -- v2, walking nested sequences.

v1 replaced only TOP-LEVEL UID tags. DICOM nests: ReferencedImageSequence,
SourceImageSequence and the dose-report ContentSequence all carry their own UIDs, and
those were left untouched. Two consequences, one obvious and one not:

  * the originals were still readable -- those UIDs embed the scanner serial and the
    real study date (`...1107.5.1.4.<serial>.<date+seq>`), so blanking the top-level
    tags left the same facts one level down; and

  * the references BROKE. Those sequences link a derived image to the slice it came
    from. v1 changed the source's SOPInstanceUID and not the reference to it, so every
    link pointed at a UID that no longer existed. That failure would have surfaced for
    whoever tried to open the study, not for me.

So the same uid_map is applied recursively: consistency is what keeps the study
assemblable, and applying it everywhere is what removes the identifiers.

Dates and device text inside sequences get the same treatment for the same reason.
"""
import datetime, glob, json, os, random
import pydicom
from pydicom.uid import generate_uid

SRC = os.environ.get('DICOM_SRC', 'work/originals')
DST = os.environ.get('DICOM_DST', 'work/deid')
MAP = os.environ.get('DICOM_KEY', 'work/REIDENTIFY-KEY.json')

EMPTY = ['PatientName','PatientID','PatientBirthDate','PatientAddress','PatientTelephoneNumbers',
         'PatientMotherBirthName','OtherPatientIDs','OtherPatientNames','IssuerOfPatientID',
         'AccessionNumber','StudyID','InstitutionName','InstitutionAddress',
         'InstitutionalDepartmentName','ReferringPhysicianName','PerformingPhysicianName',
         'OperatorsName','PhysiciansOfRecord','RequestingPhysician','NameOfPhysiciansReadingStudy',
         'RequestingService','DeviceSerialNumber','StationName','AdmissionID',
         'CurrentPatientLocation','MilitaryRank','BranchOfService','MedicalRecordLocator',
         'PatientReligiousPreference','ResponsiblePerson','ResponsibleOrganization',
         'ContentCreatorName','ScheduledPerformingPhysicianName','OrderCallbackPhoneNumber']
# Site-specific strings to strip from free-text fields: scanner serials, station
# names, the PACS application title. These vary per installation and are NOT in this
# repo -- a list of the identifiers you are removing is itself identifying, and it
# names a specific clinic's equipment.
#
# Format: one string per line. Absent file = the tag-level rules still run, which
# covers DeviceSerialNumber and StationName; this catches the same values where they
# turn up in a free-text description or a nested content sequence.
_DEV = os.environ.get('DICOM_DEVICE_STRINGS', '/etc/deid/device-strings.txt')
DEVICE_TEXT = set()
if os.path.exists(_DEV):
    DEVICE_TEXT = {l.strip() for l in open(_DEV) if l.strip() and not l.startswith('#')}

def main():
    uid_map={}
    def newuid(old):
        old=str(old)
        if not old: return old
        if old not in uid_map: uid_map[old]=generate_uid()
        return uid_map[old]

    def shift(v,days):
        try: return (datetime.datetime.strptime(str(v)[:8],'%Y%m%d')+datetime.timedelta(days=days)).strftime('%Y%m%d')
        except Exception: return ''

    def walk(d, days):
        for el in d:
            if el.VR=='SQ':
                for item in (el.value or []): walk(item, days)
            elif el.VR=='UI' and el.value and el.keyword not in (
                    'SOPClassUID','TransferSyntaxUID','ImplementationClassUID',
                    'MediaStorageSOPClassUID','SpecificCharacterSet'):
                el.value = newuid(el.value)
            elif el.VR=='DA' and el.value:
                el.value = shift(el.value, days)
            elif el.VR=='DT' and el.value:
                s=str(el.value); el.value = shift(s[:8],days) + s[8:] if len(s)>=8 else ''
            elif el.VR in ('LO','SH','ST','LT','UT','PN','CS') and el.value:
                if any(t in str(el.value) for t in DEVICE_TEXT): el.value=''

    pats=sorted(x for x in os.listdir(SRC) if os.path.isdir(os.path.join(SRC,x)))
    rng=random.Random(20260909); key={}
    for i,p in enumerate(pats,1):
        days=rng.randint(-3650,-365); pseudo=f'CT-{i:03d}'
        key[p]={'pseudo_id':pseudo,'date_shift_days':days}
        n=0
        for f in sorted(glob.glob(f'{SRC}/{p}/**/*.dcm',recursive=True)):
            try: ds=pydicom.dcmread(f)
            except Exception: continue
            ds.remove_private_tags()
            for t in EMPTY:
                if t in ds:
                    try: setattr(ds,t,'')
                    except Exception: pass
            walk(ds, days)                       # <-- recursive: UIDs, dates, device text
            ds.PatientName=pseudo; ds.PatientID=pseudo
            ds.PatientIdentityRemoved='YES'
            ds.DeidentificationMethod='identifiers removed; private tags removed; UIDs remapped recursively; dates shifted'
            if hasattr(ds,'file_meta') and 'MediaStorageSOPInstanceUID' in ds.file_meta:
                ds.file_meta.MediaStorageSOPInstanceUID=ds.SOPInstanceUID
            op=os.path.join(DST,pseudo,os.path.relpath(f,os.path.join(SRC,p)))
            os.makedirs(os.path.dirname(op),exist_ok=True)
            ds.save_as(op, enforce_file_format=True); n+=1
        key[p]['files']=n
        print(f'  {p} -> {pseudo}: {n} files, dates shifted {days} days', flush=True)
    key['_uid_map_size']=len(uid_map)
    json.dump(key,open(MAP,'w'),indent=1); os.chmod(MAP,0o600)
    print(f'\nUIDs regenerated (incl. nested): {len(uid_map)}')

main()
