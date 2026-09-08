#!/usr/bin/env python3
"""Transcribe the BEEPED audio and check nothing sensitive survives.

This is the check that matters. Everything before it verifies that the plan was
carried out; this asks whether the finished file still says the thing.
"""
import glob, json, os, re, time
from faster_whisper import WhisperModel
SRC=os.environ.get('BEEPED_DIR','work/audio-beeped')
OUT=os.environ.get('OUT_DIR','work/transcripts-beeped')
os.makedirs(OUT,exist_ok=True)
# Names to search for in the FINISHED audio. Loaded locally for the same reason as
# above: this list is the PII. Without it the check still catches digits and numbers
# spoken as words, which is the higher-risk half.
NAMES = set()
_NF = os.environ.get('SPOKEN_PII_NAMES', '/etc/deid/given-names.txt')
if os.path.exists(_NF):
    NAMES = {l.strip().lower() for l in open(_NF) if l.strip() and not l.startswith('#')}
# v1 of this check looked only for DIGITS and names, so "seven one seven" -- a phone
# number read aloud as words -- scored zero survivors while being plainly audible.
NUMWORDS={'zero','one','two','three','four','five','six','seven','eight','nine','ten','oh','double','triple'}
m=WhisperModel('large-v3',device='cpu',compute_type='int8',cpu_threads=4)
findings=[]
for f in sorted(glob.glob(f'{SRC}/*.wav')):
    b=os.path.basename(f); t=time.time()
    segs,_=m.transcribe(f, word_timestamps=True, vad_filter=True, beam_size=5,
        condition_on_previous_text=False, language='en',
        no_repeat_ngram_size=3, repetition_penalty=1.15,
        hallucination_silence_threshold=2.0, compression_ratio_threshold=2.0,
        log_prob_threshold=-0.8,
        vad_parameters=dict(min_silence_duration_ms=400, speech_pad_ms=200))
    S=[]; hits=[]
    for s in segs:
        S.append({'start':s.start,'end':s.end,'text':s.text,
                  'words':[{'w':w.word,'s':w.start,'e':w.end} for w in (s.words or [])]})
        for w in (s.words or []):
            tok=w.word.strip().strip('.,!?;:"\'').lower()
            d=re.sub(r'[^0-9]','',tok)
            if tok in NAMES or len(d)>=4:
                hits.append({'t':round(w.start,1),'w':w.word.strip(),'why':'name/digits'})
        # a RUN of spoken number words is a number being read out
        ws=[(w.word.strip().strip('.,!?;:\"\'').lower(), w) for w in (s.words or [])]
        i=0
        while i<len(ws):
            if ws[i][0] in NUMWORDS:
                j=i
                while j<len(ws) and ws[j][0] in NUMWORDS: j+=1
                if j-i>=3:
                    hits.append({'t':round(ws[i][1].start,1),
                                 'w':' '.join(x[0] for x in ws[i:j]),'why':'number spoken as words'})
                i=j
            else: i+=1
    json.dump({'file':b,'segments':S,'survivors':hits},
              open(os.path.join(OUT,b.replace('.wav','.json')),'w'),ensure_ascii=False,indent=1)
    findings.append((b,len(hits),hits[:6]))
    print(f'  {b:<34} {time.time()-t:>5.0f}s   survivors: {len(hits)}'
          + (f'  {[h["w"] for h in hits[:5]]}' if hits else ''), flush=True)
tot=sum(n for _,n,_ in findings)
print(f'\n=== sensitive tokens still audible after beeping: {tot} ===')
