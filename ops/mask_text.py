#!/usr/bin/env python3
"""Mask identities, contacts, credentials and IDs in exported text.

Names and organisations come from a map (real value -> pseudonym). Emails, phone numbers,
platform IDs and credential-shaped strings are handled by PATTERN rather than by list,
because no list of them could be complete -- one export here held 363 distinct email
addresses and enumerating them by hand would miss the next one.

Message text, dates and money are KEPT. Removing them leaves a corpus that is technically
clean and worth nothing; the point is data that still reads as a real project while
naming nobody.

THREE THINGS THE MATCHING MUST GET RIGHT, each learned from a pass that reported clean:

  * ONE MERGED ALTERNATION, LONGEST FIRST. Alternation is leftmost-first, so "First Last"
    must be tried before "First" or the surname is stranded next to a pseudonym.
  * CASE-INSENSITIVE. A case-sensitive pass masked the lowercase forms in structured
    fields and left the shouted and capitalised forms in the message text -- the same
    name, surviving because someone typed it differently.
  * SEPARATOR-INSENSITIVE. Chat exports write TWO spaces around an @mention, so an exact
    single-space literal misses "First  Last" -- and also "First-Last", "FirstLast", the
    name as a domain, and an email flattened into a URL slug.

MAP_JSON maps each original value to its replacement. Keep it out of the repository and
out of the delivery: it is the re-identification key.

Usage: mask_text.py SRC_DIR DST_DIR MAP_JSON
"""
import json, os, re, shutil, sys

TEXT = ('.csv', '.json', '.md', '.html', '.htm', '.txt', '.xml', '.log', '.tsv')


def build(map_json):
    mapping = json.load(open(map_json))
    literals = sorted(mapping, key=len, reverse=True)      # longest first

    def rx_for(v):
        parts = [p for p in re.split(r'[^A-Za-z0-9]+', v) if p]
        return r'[^A-Za-z0-9]{0,3}'.join(re.escape(p) for p in parts) if parts else None

    alts = [r for r in (rx_for(k) for k in literals) if r]
    rx = re.compile(r'(?<![A-Za-z0-9])(' + '|'.join(alts) + r')(?![A-Za-z0-9])',
                    re.IGNORECASE)
    # the matched text no longer equals the key, so canonicalise on alphanumerics only
    canon = {re.sub(r'[^a-z0-9]', '', k.lower()): v for k, v in mapping.items()}
    return rx, canon


EMAIL = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
APIKEY = re.compile(r'(?:AIza[0-9A-Za-z_\-]{35}|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}'
                    r'|ghp_[A-Za-z0-9]{30,}|xox[baprs]-[A-Za-z0-9-]{10,}|SG\.[A-Za-z0-9_\-]{20,})')
PWD = re.compile(r'(?i)((?:password|passwd|pwd|pass)\s*(?:is|:|=|-)\s*["\']?)([^\s"\'\\,;<>]{6,40})')
PHONE = re.compile(r'(?<![\d.\-])(?:\+?\d{1,3}[ -]?)?\(?\d{3}\)?[ -]?\d{3}[ -]?\d{4}(?![\d.\-])')
LONGNUM = re.compile(r'(?<![\d.])\d{9,19}(?![\d.])')
TOKENURL = re.compile(r'(https?://[^\s"\'<>]*?[?&](?:key|token|auth|password|secret|session)=)'
                      r'[^\s"\'<>&]+')


def main(src_dir, dst_dir, map_json):
    rx, canon = build(map_json)
    emails, nums = {}, {}

    def email_sub(m):
        v = m.group(0).lower()
        emails.setdefault(v, f'person{len(emails) + 1:03d}@example.com')
        return emails[v]

    def num_sub(m):
        v = m.group(0)
        nums.setdefault(v, str(10 ** (len(v) - 1) + len(nums)))   # same length, not real
        return nums[v]

    def mask(t):
        t = rx.sub(lambda m: canon[re.sub(r'[^a-z0-9]', '', m.group(1).lower())], t)
        t = APIKEY.sub('REDACTED_API_KEY', t)
        t = PWD.sub(lambda m: m.group(1) + 'REDACTED_CREDENTIAL', t)
        t = TOKENURL.sub(lambda m: m.group(1) + 'REDACTED', t)
        t = EMAIL.sub(email_sub, t)
        t = LONGNUM.sub(num_sub, t)
        return PHONE.sub(lambda m: 'X' * len(m.group(0)), t)

    masked = copied = 0
    for root, _, files in os.walk(src_dir):
        for f in files:
            src = os.path.join(root, f)
            # paths carry names too
            dst = mask(src.replace(src_dir, dst_dir, 1))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if f.lower().endswith(TEXT):
                open(dst, 'w', encoding='utf-8').write(
                    mask(open(src, encoding='utf-8', errors='replace').read()))
                masked += 1
            else:
                # NOT clean: an archive copied through carries its contents unmasked.
                # Handle images separately, then rebuild archives -- see repack_archives.py
                shutil.copy2(src, dst)
                copied += 1

    print(f'masked {masked} text files, copied {copied} others')
    print(f'  distinct emails replaced : {len(emails)}')
    print(f'  distinct long numbers    : {len(nums)}')
    print('  NOW: mask images, rebuild archives, then scan_output.py')
    return 0


if __name__ == '__main__':
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1].rstrip('/'), sys.argv[2].rstrip('/'), sys.argv[3]))
