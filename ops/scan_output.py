#!/usr/bin/env python3
"""Search the OUTPUT for values known to be in the INPUT. Looks inside archives.

This is the only check in this pipeline that has ever caught anything. Every gate that
asked "did my tool report success?" passed while the data was still leaking.

SEPARATORS VARY, WORD BOUNDARIES MUST NOT. Matching exact literals with single spaces
missed the same name written with two spaces (chat exports do that around an @mention),
with a hyphen, with no space at all, as a domain, and flattened into a URL slug. Dozens
of original values survived a pass already reported clean -- because the check matched
literally too, and so agreed with the masker.

The tempting shortcut is worse: strip punctuation from the whole document and
substring-match. Adjacent words then fuse, and "and resolve" contains the name "Andres".
Each value therefore becomes its alphanumeric runs joined by a short separator class,
anchored at both ends.

VALUES_JSON: a JSON object or array; every string key (or element) is treated as an
original value to search for. Keep that file out of the repository -- a list of the names
you are removing is itself the data you are removing.

Usage: scan_output.py OUTPUT_DIR VALUES_JSON [MIN_LEN]
"""
import collections, glob, json, os, re, sys, zipfile

TEXT = ('.csv', '.json', '.md', '.html', '.htm', '.txt', '.xml', '.log', '.tsv', '.yaml', '.yml')


def rx_for(value, min_len):
    parts = [p for p in re.split(r'[^A-Za-z0-9]+', value) if p]
    if not parts or sum(len(p) for p in parts) < min_len:
        return None
    body = r'[^A-Za-z0-9]{0,3}'.join(re.escape(p) for p in parts)
    return re.compile(r'(?<![A-Za-z0-9])' + body + r'(?![A-Za-z0-9])', re.IGNORECASE)


def load_values(path):
    raw = json.load(open(path))
    if isinstance(raw, dict):
        return list(raw.keys())
    return [v for v in raw if isinstance(v, str)]


def check(name, data, needles, hits):
    text = data.decode('utf-8', 'ignore')
    for value, rx in needles:
        m = rx.search(text)
        if m:
            s, e = max(0, m.start() - 40), min(len(text), m.end() + 40)
            hits[value].append((name, text[s:e].replace('\n', ' ')))


def main(out_dir, values_json, min_len=5):
    needles = [(v, r) for v, r in ((v, rx_for(v, min_len)) for v in load_values(values_json)) if r]
    print(f'{len(needles)} original values to search for')
    hits, files = collections.defaultdict(list), 0
    for f in sorted(glob.glob(f'{out_dir}/**/*', recursive=True)):
        if not os.path.isfile(f):
            continue
        files += 1
        if f.lower().endswith('.zip'):
            try:
                zf = zipfile.ZipFile(f)
            except Exception as e:
                print(f'  unreadable archive {f}: {e}')
                continue
            for n in zf.namelist():
                if n.lower().endswith(TEXT):
                    check(f'{f}::{n}', zf.read(n), needles, hits)
        elif f.lower().endswith(TEXT):
            check(f, open(f, 'rb').read(), needles, hits)

    print(f'searched {files} files')
    if not hits:
        print('\nCLEAN: no original value found in the output.')
        return 0
    print(f'\n*** {len(hits)} original values still present:\n')
    for value, where in sorted(hits.items()):
        name, ctx = where[0]
        print(f'   {value!r} in {len(where)} file(s)')
        print(f'        {os.path.basename(name)[:48]} :: ...{ctx}...')
    return 1


if __name__ == '__main__':
    if len(sys.argv) not in (3, 4):
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1].rstrip('/'), sys.argv[2],
                  int(sys.argv[3]) if len(sys.argv) == 4 else 5))
