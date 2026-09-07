#!/usr/bin/env python3
"""Scan EVERY object in a repository's history for the leak classes a name gate misses.

The earlier gates in this pipeline answer "did we remove the developers?" -- names,
emails, known secret formats. They all reported clean on an estate that was, at the
same time, carrying real customers' payment card numbers.

This scans for a different question: "what is in here that belongs to somebody who
never worked on this code?" Four classes, each of which passed every prior gate:

  1. CARDHOLDER DATA. Card numbers validated with the Luhn checksum and screened
     against the standard test numbers, plus CVV fields. A stored CVV is prohibited
     outright, so any hit is serious regardless of count.
  2. BULK PERSONAL DATA. Logs, CSV/SQL dumps and upload folders holding many rows of
     names, phone numbers or emails. Scrubbing developer emails does not touch these
     -- it makes them *look* clean, because the email check comes back zero.
  3. PLAIN-TEXT CREDENTIALS. `storePassword 'x'`, `MQTT_PASSWORD "y"`, a database URL
     with a password in it. Format-based secret scanners miss all of these: they are
     not AWS keys or PEM blocks, they are ordinary-looking config values.
  4. BINARY METADATA. Absolute source paths inside images -- see
     lib/strip_image_metadata.py for why --replace-text cannot reach them.

WHY EVERY OBJECT, NOT THE CHECKOUT: a sample ships with full history. Anything the
current tree no longer shows is still one `git checkout` away. Rules derived from the
working tree miss spellings that exist only in older commits -- verified here, where a
working-tree-derived rule set left 667 historical blobs still leaking.

Read-only. Nothing is modified. Exit status 1 if anything is found.

Usage: 7_scan_history.py REPO [REPO...]
"""
import re
import subprocess
import sys
import collections

MAX_BLOB = 40 * 1024 * 1024

CARD = re.compile(rb'\b(?:\d[ -]?){12,18}\d\b')
CVV = re.compile(rb'(?i)["\']?cvv2?["\']?\s*[:=]\s*["\']?\d{3,4}["\']?')
PWD = re.compile(
    rb'''(?i)(?:password|passwd|pwd|secret|api[_-]?key|token|storepassword|keypassword)'''
    rb'''["\']?\s*[:=]\s*["\']([^"\'\s${}<>]{8,80})["\']''')
DBURL = re.compile(rb'(?i)\b[a-z][a-z0-9+.-]{2,15}://[^\s:@/"\']{1,40}:([^\s:@/"\']{4,60})@')
WINPATH = re.compile(rb'[A-Za-z]:\\[A-Za-z0-9 _.\\-]{6,120}')
HOMEPATH = re.compile(rb'(?:/Users/|/home/)[A-Za-z][A-Za-z0-9._-]{2,20}')
EMAIL = re.compile(rb'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
PHONE = re.compile(rb'\b(?:\+?1[ -]?)?\(?[2-9]\d{2}\)?[ -]?\d{3}[ -]?\d{4}\b')

DATA_FILE = re.compile(r'(?i)\.(log|csv|tsv|sql|dump|xls|xlsx)$|(^|/)uploads?/|(^|/)dumps?/')
ARTEFACT = re.compile(r'(?i)\.(jks|keystore|p12|pfx|apk|aab|ipa|mobileprovision|ppk)$')

# placeholder values that are not credentials
PLACEHOLDER = re.compile(
    rb'(?i)^(redacted|changeme|password|secret|your[_-]?\w*|example\w*|test\w*|dummy|'
    rb'placeholder|xxx+|none|null|undefined|true|false|\d+|[a-f0-9]{7,40})$')
TEST_CARDS = {'4111111111111111', '4242424242424242', '5555555555554444',
              '4000000000000002', '378282246310005', '6011111111111117',
              '5105105105105100', '4012888888881881', '30569309025904',
              '3566002020360505', '6221260000000000'}


def luhn(n: str) -> bool:
    total = 0
    for i, c in enumerate(reversed(n)):
        v = int(c)
        if i % 2:
            v *= 2
            if v > 9:
                v -= 9
        total += v
    return total % 10 == 0


def real_pan(raw: bytes) -> bool:
    n = re.sub(rb'[ -]', b'', raw).decode()
    if len(n) not in (13, 14, 15, 16, 19) or n in TEST_CARDS:
        return False
    if len(set(n)) <= 4:                       # 4111..., 0000..., sequential filler
        return False
    return luhn(n) and n[0] in '3456'


def scan(repo: str):
    paths = {}
    for line in subprocess.run(['git', '-C', repo, 'rev-list', '--all', '--objects'],
                               capture_output=True, text=True).stdout.split('\n'):
        if ' ' in line:
            sha, p = line.split(' ', 1)
            paths[sha] = p

    found = collections.defaultdict(collections.Counter)
    proc = subprocess.Popen(
        ['git', '-C', repo, 'cat-file', '--batch-all-objects', '--batch', '--buffer'],
        stdout=subprocess.PIPE)
    f = proc.stdout
    while True:
        hdr = f.readline()
        if not hdr:
            break
        parts = hdr.split()
        if len(parts) < 3:
            continue
        sha, typ, size = parts[0].decode(), parts[1], int(parts[2])
        data = f.read(size)
        f.read(1)
        if typ != b'blob' or size > MAX_BLOB:
            continue
        path = paths.get(sha, '<unreachable>')
        binary = b'\x00' in data[:8000]

        if not binary:
            for m in CARD.finditer(data):
                if real_pan(m.group(0)):
                    found['cardholder data'][path] += 1
            n = len(CVV.findall(data))
            if n:
                found['CVV fields'][path] += n
            for rx in (PWD, DBURL):
                for m in rx.finditer(data):
                    if not PLACEHOLDER.match(m.group(1)):
                        found['plain-text credential'][path] += 1
            if DATA_FILE.search(path):
                rows = data.count(b'\n')
                people = len(set(EMAIL.findall(data))) + len(set(PHONE.findall(data)))
                if rows > 200 and people > 20:
                    found['bulk personal data'][f'{path} ({rows} rows, {people} identifiers)'] += 1
        else:
            for rx in (WINPATH, HOMEPATH):
                n = len(rx.findall(data))
                if n:
                    found['path inside binary'][path] += n

        if ARTEFACT.search(path):
            found['credential/artefact file'][path] += 1

    return found


def main(repos):
    total = 0
    for repo in repos:
        found = scan(repo)
        hits = sum(sum(c.values()) for c in found.values())
        total += hits
        print(f'\n=== {repo}: {"CLEAN" if not hits else str(hits) + " HITS"}')
        for cls in sorted(found):
            c = found[cls]
            print(f'  {cls}: {sum(c.values())} in {len(c)} file(s)')
            for p, n in c.most_common(6):
                print(f'      x{n:<6} {p}')
    print(f'\n=== total findings: {total} ===')
    return 1 if total else 0


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1:]))
