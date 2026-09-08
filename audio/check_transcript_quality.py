#!/usr/bin/env python3
"""Decide whether a transcript is good enough to base redaction on.

WHY THIS EXISTS: on a 24-file call-centre set, speech recognition worked on English
and produced structurally broken text in Punjabi, Kannada and Bengali. The broken
output is not obviously broken -- it is fluent-looking, arrives at a confident words-
per-minute rate, and the language detector reports 1.00 confidence.

That is the dangerous case. A PII detector reading nonsense finds no names and no
numbers, reports the file clean, and the file ships with a phone number still in it.

Words per minute does NOT detect this. The worst file in that set scored 146 wpm --
higher than several files that were fine.

What does detect it, without any knowledge of the language:

  SCRIPT PURITY   Punjabi is written in Gurmukhi. Text drifting into Bengali or Latin
                  is the model guessing. Below ~95% in one script means trouble.
  MIXED WORDS     A single word containing two scripts is not a word.
  INVALID CHARS   U+FFFD and private-use code points mean the decoder emitted
                  something that is not text.
  DEAD SEGMENTS   A 200-second segment holding 15 words is not transcription, it is
                  the model filling silence. Those seconds are UNCHECKED, not clean.

Exit status 1 if any transcript fails, so this can gate a pipeline.

Usage: check_transcript_quality.py TRANSCRIPT.json [...]
"""
import json, sys, collections, unicodedata

RANGES = [(0x0900,0x097F,'Devanagari'), (0x0A00,0x0A7F,'Gurmukhi'),
          (0x0C80,0x0CFF,'Kannada'),    (0x0980,0x09FF,'Bengali'),
          (0x0B80,0x0BFF,'Tamil'),      (0x0A80,0x0AFF,'Gujarati'),
          (0x0B00,0x0B7F,'Oriya'),      (0x0D00,0x0D7F,'Malayalam'),
          (0x0C00,0x0C7F,'Telugu'),     (0x0041,0x007A,'Latin'),
          (0x0600,0x06FF,'Arabic'),     (0x0400,0x04FF,'Cyrillic')]
MIN_PURITY = 95.0
DEAD_MIN_SEC = 20.0
DEAD_MAX_WPM = 40.0

def script_of(ch):
    o = ord(ch)
    for lo, hi, name in RANGES:
        if lo <= o <= hi:
            return name
    return None

def assess(path):
    r = json.load(open(path))
    text = ' '.join(s['text'] for s in r['segments'])
    counts = collections.Counter(x for x in (script_of(c) for c in text) if x)
    total = sum(counts.values()) or 1
    main, n = counts.most_common(1)[0] if counts else ('-', 0)
    purity = 100 * n / total
    invalid = text.count('�') + sum(1 for c in text if unicodedata.category(c) == 'Co')
    mixed = sum(1 for w in text.split()
                if len({script_of(c) for c in w if script_of(c)}) > 1)
    dead = sum(s['end'] - s['start'] for s in r['segments']
               if (s['end'] - s['start']) > DEAD_MIN_SEC
               and len(s.get('words') or []) / (((s['end'] - s['start']) or 1) / 60) < DEAD_MAX_WPM)
    ok = purity >= MIN_PURITY and invalid == 0 and mixed == 0
    return dict(file=r.get('file', path), lang=r.get('detected_language', '?'),
                words=r.get('n_words', 0), main=main, purity=purity,
                invalid=invalid, mixed=mixed, dead=dead,
                duration=r.get('duration', 0), ok=ok)

def main(paths):
    print(f"{'file':<34}{'lang':>5}{'words':>7}{'script':>12}{'purity':>8}"
          f"{'invalid':>9}{'mixed':>7}{'dead s':>8}  verdict")
    print('-' * 104)
    bad = 0
    for p in paths:
        a = assess(p)
        if not a['ok']:
            bad += 1
        print(f"  {a['file'][:32]:<32}{a['lang']:>5}{a['words']:>7}{a['main'][:10]:>12}"
              f"{a['purity']:>7.0f}%{a['invalid']:>9}{a['mixed']:>7}{a['dead']:>8.0f}"
              f"  {'USABLE' if a['ok'] else 'DEGRADED — do not redact from this'}")
    print(f"\n{len(paths) - bad} usable, {bad} degraded of {len(paths)}")
    if bad:
        print("\nA degraded transcript must not be used to drive redaction. The detector will\n"
              "find nothing in it and the file will look finished. Route these to a human.")
    return 1 if bad else 0

if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1:]))
