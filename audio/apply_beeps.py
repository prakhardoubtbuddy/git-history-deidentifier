#!/usr/bin/env python3
"""Beep the flagged spans, snapping each one outward to real silence.

WHY: the first attempt trusted the recogniser's word timestamps and added 0.3s of
padding. On the phone-number file the recogniser placed the number at 10.01s when the
speaker actually began around 8.0s, so ~1.7s of a spoken phone number stayed audible.
A tone check passed and the survivor count read zero, because the leaked words were
"seven one seven" -- not digits, not a name.

So do not trust the timestamp. Take it as a hint, then walk outward through the actual
audio until the level drops to silence for long enough to be a real gap between
utterances. The beep then covers the whole utterance whatever the timestamp said.

Bounded by MAX_EXTEND so a span in continuous speech cannot swallow the call.
"""
import json, math, os, struct, sys, wave

SRC=os.environ.get('AUDIO','work/audio')
DST=os.environ.get('BEEPED','work/audio-beeped')
SPANS=os.environ.get('SPANS','work/pii-spans.json')
TRANS=os.environ.get('TRANSCRIPTS','work/transcripts')
FREQ=1000.0; LEVEL=0.22; FADE=0.010
WIN=0.02            # 20 ms analysis window
SILENCE_DB=-45.0    # below this counts as a gap
GAP=0.18            # this much continuous quiet ends the utterance
MAX_EXTEND=3.0      # never grow a span by more than this on either side

def frame_db(x):
    if not x: return -99.0
    e=sum(v*v for v in x)/len(x)
    return 20*math.log10(math.sqrt(e)/32768+1e-12)

def neighbours(words, a, b):
    """End of the last word before the span, start of the first word after.

    This is the bound the first rebuild lacked. Snapping to silence alone let a
    span grow through a pause and swallow ordinary speech; the recogniser may put
    a word at the wrong TIME, but the ORDER of words is reliable, so the previous
    word's end is a hard floor and the next word's start a hard ceiling.
    """
    lo, hi = 0.0, 1e9
    for w in words:
        if w['e'] <= a + 0.05: lo = max(lo, w['e'])
        if w['s'] >= b - 0.05: hi = min(hi, w['s']); break
    return lo, hi

def snap(samples, sr, a, b, lo=0.0, hi=1e9):
    """Grow [a,b] outward until GAP seconds of continuous silence on each side."""
    n=len(samples); w=max(1,int(WIN*sr)); need=max(1,int(GAP/WIN))
    i=int(a*sr); quiet=0; limit=int(max(0,a-MAX_EXTEND,lo)*sr)
    while i-w > limit:
        if frame_db(samples[i-w:i]) < SILENCE_DB:
            quiet+=1
            if quiet>=need: break
        else: quiet=0
        i-=w
    new_a=max(0.0, i/sr)
    j=int(b*sr); quiet=0; limit=int(min(n,(b+MAX_EXTEND)*sr,hi*sr))
    while j+w < limit:
        if frame_db(samples[j:j+w]) < SILENCE_DB:
            quiet+=1
            if quiet>=need: break
        else: quiet=0
        j+=w
    new_b=min(n/sr, j/sr)
    return new_a, new_b

os.makedirs(DST, exist_ok=True)
spans=json.load(open(SPANS))
report={}
tf=ts=0; tsec=0.0; grown=0.0
for fname, meta in sorted(spans.items()):
    src=os.path.join(SRC,fname)
    if not os.path.exists(src): continue
    with wave.open(src,'rb') as w:
        nch,sw,sr,nfr = w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getnframes()
        raw=bytearray(w.readframes(nfr))
    if sw!=2 or nch!=1: print(f'  SKIP {fname}'); continue
    n=len(raw)//2
    samples=struct.unpack(f'<{n}h', bytes(raw))
    tp=os.path.join(TRANS, fname.replace('.wav','.json'))
    words=[]
    if os.path.exists(tp):
        for sg in json.load(open(tp))['segments']:
            words += (sg.get('words') or [])
    words.sort(key=lambda w: w['s'])
    out_spans=[]
    for sp in meta['spans']:
        lo,hi = neighbours(words, sp['start'], sp['end'])
        a,b = snap(samples, sr, sp['start'], sp['end'], lo, hi)
        grown += (sp['start']-a)+(b-sp['end'])
        out_spans.append({'start':a,'end':b,'reason':sp['reason'],'heard':sp['heard'],
                          'orig_start':sp['start'],'orig_end':sp['end']})
    # merge any that now overlap
    out_spans.sort(key=lambda s:s['start']); merged=[]
    for s in out_spans:
        if merged and s['start']<=merged[-1]['end']:
            merged[-1]['end']=max(merged[-1]['end'],s['end'])
            merged[-1]['heard']+=' '+s['heard']
        else: merged.append(s)
    beeped=0.0
    for sp in merged:
        a=max(0,int(sp['start']*sr)); b=min(n,int(sp['end']*sr))
        if b<=a: continue
        L=b-a; fade=max(1,int(FADE*sr))
        for i in range(L):
            env=min(1.0, i/fade, (L-i)/fade)
            v=int(LEVEL*env*32767*math.sin(2*math.pi*FREQ*(i/sr)))
            struct.pack_into('<h', raw, (a+i)*2, max(-32768,min(32767,v)))
        beeped += (b-a)/sr
    with wave.open(os.path.join(DST,fname),'wb') as w:
        w.setnchannels(nch); w.setsampwidth(sw); w.setframerate(sr); w.writeframes(bytes(raw))
    report[fname]={'spans':merged}
    tf+=1; ts+=len(merged); tsec+=beeped
    print(f'  {fname:<34} {len(meta["spans"]):>2} -> {len(merged):>2} spans  '
          f'{beeped:>5.1f}s ({100*beeped/(n/sr):.1f}%)')
json.dump(report, open(os.environ.get('SPANS_FINAL','work/pii-spans-final.json'),'w'), indent=1)
print(f'\n{tf} files, {ts} beeps, {tsec:.1f}s replaced (grown {grown:.1f}s beyond the timestamps)')
