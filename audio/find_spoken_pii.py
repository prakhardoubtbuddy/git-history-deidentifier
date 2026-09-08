#!/usr/bin/env python3
"""Find spoken personal information -- second version.

v1 missed the two most damaging items in the set: a phone number spoken in full
(it arrives as ONE token with hyphens, so a bare digit test rejects it) and a
surname spelled out letter by letter. It also produced junk, because these calls say
"sir" constantly and v1 treated that as a name marker.

Both failures point the same way: the rules were written for how numbers and names
look in tidy text, not for how a call-centre transcript actually renders them.
"""
import glob, json, os, re, sys, unicodedata, collections

T=os.environ.get('TRANSCRIPTS','work/transcripts')
OUT=os.environ.get('SPANS','work/pii-spans.json')
PAD=0.30; MERGE_GAP=0.6

NUMWORDS=set("""zero one two three four five six seven eight nine ten oh double triple
eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty thirty
forty fifty sixty seventy eighty ninety hundred thousand
ek do teen char paanch panch chhe che saat aath nau das shunya
ondu eradu muru nalku aidu aaru elu entu ombattu hattu
ik dui tin chaar panj chhey satt atth""".split())
NATIVE=set("""एक दो तीन चार पांच पाँच छह सात आठ नौ दस शून्य
ਇੱਕ ਦੋ ਤਿੰਨ ਚਾਰ ਪੰਜ ਛੇ ਸੱਤ ਅੱਠ ਨੌਂ ਦਸ
ಒಂದು ಎರಡು ಮೂರು ನಾಲ್ಕು ಐದು ಆರು ಏಳು ಎಂಟು ಒಂಬತ್ತು ಹತ್ತು""".split())

# "sir"/"madam" are vocatives here, not name prefixes -- they caused v1's junk
TITLE=re.compile(r'(?i)^(mr|mrs|ms|miss|dr|prof|shri|smt)\.?$')
NAME_Q=re.compile(r'(?i)(your|the)\s+(full\s+|last\s+|first\s+|sur)?name|may i (have|know) your|who am i speaking|spell (it|that|your)')
NAME_CUE=re.compile(r'(?i)\b(my name is|this is|name is|speaking|मेरा नाम|ਮੇਰਾ ਨਾਮ|ನನ್ನ ಹೆಸರು)\b')
ADDR=re.compile(r'(?i)\b(address|pin ?code|zip ?code|postal|street|avenue|colony|sector|nagar|पता|ਪਤਾ)\b')
DOB=re.compile(r'(?i)\b(date of birth|d\.?o\.?b|birthday|born on|जन्म)\b')
EMAILW=re.compile(r'(?i)\b(email|e-mail|gmail|yahoo|hotmail|outlook|at the rate|dot com)\b')
FIN=re.compile(r'(?i)\b(card|cvv|expiry|debit|credit|otp|upi|ifsc|account number|routing|social security|ssn|bank)\b')
MEDICAL=re.compile(r'(?i)\b(accident|medical bill|hospital|doctor|surgery|diagnos|prescription|illness)\b')

COMMON=set("""the a an and or but if then so to of in on at for with from by as is are was were
be been being have has had do does did will would can could should may might must
i you he she it we they me him her us them my your his its our their this that these those
yes no not ok okay thank thanks please sorry hello hi hey bye goodbye sir madam maam ma'am
one two now here there what when where which who how why all any some more most other
right left up down out over under again just very too also only even still back well
good great fine sure right correct wrong true false today tomorrow yesterday minute second
hour day week month year time call caller calling phone number network internet computer
system service support technician customer account problem issue infection virus session""".split())


# A modest gazetteer of common given names. This is a DENYLIST and shares the
# denylist weakness: it only finds names that are on it. It is here as an extra
# net under the structural rules, never as the primary defence -- a name nobody
# listed still gets through, which is why a human pass remains necessary.
# A gazetteer of common given names, loaded from a LOCAL file that is not in this
# repo. A list of the names you are removing is itself the PII you are removing, so it
# belongs beside your data, never beside your tooling. Ship the tooling; keep the list.
#
# Format: one name per line, lowercase. Absent file = structural rules only, which is a
# weaker but still functional configuration.
#
# This is a DENYLIST and carries the denylist weakness: it only finds names on it. It
# sits UNDER the structural rules (titles, naming cues, digit runs, letter-spelling),
# never in place of them.
_GAZ = os.environ.get('SPOKEN_PII_NAMES', '/etc/deid/given-names.txt')
FIRSTNAMES = set()
if os.path.exists(_GAZ):
    FIRSTNAMES = {l.strip().lower() for l in open(_GAZ) if l.strip() and not l.startswith('#')}

def clean(w): return unicodedata.normalize('NFKC',w).strip().strip('.,!?;:"\'()[]।॥').lower()
def digits_only(w): return re.sub(r'[^0-9]','',w)

def numlike(w):
    c=clean(w)
    if not c: return 0
    d=digits_only(c)
    # A hyphenated number arrives as one token: strip separators, then count the
    # digits. Testing the raw token against \d+ rejects it and the number survives.
    if d and re.fullmatch(r'[0-9\-\.\s\(\)]+',c): return len(d)
    if c in NUMWORDS or c in NATIVE: return 1
    return 0

def is_spelling(words,i):
    """M-O-R-A-G-A as one token, or a run of single letters."""
    c=clean(words[i]['w'])
    if re.fullmatch(r'(?:[a-z][-\s]){2,}[a-z]',c): return i+1
    j=i; n=0
    while j<len(words) and re.fullmatch(r'[a-z]',clean(words[j]['w'])): j+=1; n+=1
    return j if n>=3 else i

def scan(rec):
    spans=[]; segs=rec['segments']
    def add(s,e,reason,heard): spans.append({'start':s,'end':e,'reason':reason,'heard':heard})
    for si,seg in enumerate(segs):
        words=seg.get('words') or []; text=seg.get('text','')
        ctx=None
        for rx,lab in ((FIN,'financial context'),(DOB,'date-of-birth context'),
                       (ADDR,'address context'),(EMAILW,'email context'),
                       (MEDICAL,'health information')):
            if rx.search(text): ctx=lab; break
        if ctx=='health information':
            add(seg['start'],seg['end'],ctx,text.strip()[:60])
        i=0
        while i<len(words):
            n=numlike(words[i]['w'])
            if n:
                j=i; total=0
                while j<len(words) and numlike(words[j]['w']):
                    total+=numlike(words[j]['w']); j+=1
                if total>=4 or ctx:
                    add(words[i]['s'],words[j-1]['e'],
                        ctx or f'number sequence ({total} digits)',
                        ' '.join(w['w'] for w in words[i:j]).strip())
                i=max(j,i+1); continue
            k=is_spelling(words,i)
            if k>i:
                add(words[i]['s'],words[k-1]['e'],'spelled out letter by letter',
                    ' '.join(w['w'] for w in words[i:k]).strip())
                i=k; continue
            # a known given name anywhere -- catches a bare first name mid-sentence,
            # which has no title or cue in front of it to trigger on
            if clean(words[i]['w']) in FIRSTNAMES:
                add(words[i]['s'],words[i]['e'],'known given name',words[i]['w'].strip())
            i+=1
        # a name spoken right after a title
        for k,w in enumerate(words):
            if TITLE.match(clean(w['w'])) and k+1<len(words):
                nx=words[k+1]
                if clean(nx['w']) not in COMMON:
                    add(nx['s'],nx['e'],'name after title',nx['w'].strip())
        # "my name is X" / "this is X" -- take only the 1-2 words RIGHT AFTER the cue.
        # v2 flagged every uncommon word in the sentence, so "this is spyware" and
        # "this is your router" produced 25 spans in one call. The name follows the
        # cue immediately or not at all.
        seq=[clean(w['w']) for w in words]
        for k in range(len(seq)-1):
            two=' '.join(seq[k:k+2]); three=' '.join(seq[k:k+3])
            if three.startswith('my name is') or two=='this is' or three=='name is':
                off = 3 if three.startswith('my name is') else (2 if two=='this is' else 2)
                for w in words[k+off:k+off+2]:
                    c=clean(w['w'])
                    if c and c not in COMMON and not numlike(w['w']) and len(c)>2:
                        add(w['s'],w['e'],'name after naming cue',w['w'].strip())
                    break
        # THE ANSWER to "may I have your name?" lands in a LATER segment
        if NAME_Q.search(text):
            for nxt in segs[si+1:si+3]:
                for w in (nxt.get('words') or [])[:6]:
                    c=clean(w['w'])
                    if c and c not in COMMON and not numlike(w['w']) and len(c)>1:
                        add(w['s'],w['e'],'answer to a name question',w['w'].strip())
    spans.sort(key=lambda s:s['start'])
    merged=[]
    for s in spans:
        s=dict(s,start=max(0.0,s['start']-PAD),end=s['end']+PAD)
        if merged and s['start']<=merged[-1]['end']+MERGE_GAP:
            m=merged[-1]; m['end']=max(m['end'],s['end'])
            if s['reason'] not in m['reason']: m['reason']+=' + '+s['reason']
            m['heard']=(m['heard']+' '+s['heard']).strip()
        else: merged.append(s)
    return merged

out={}; tot=0; totd=0.0
for p in sorted(glob.glob(f'{T}/*.json')):
    r=json.load(open(p)); sp=scan(r)
    out[r['file']]={'duration':r['duration'],'detected_language':r['detected_language'],
                    'folder_language':r['folder_language'],'spans':sp}
    d=sum(s['end']-s['start'] for s in sp); tot+=len(sp); totd+=d
    print(f"  {r['file']:<34} {len(sp):>3} spans  {d:>6.1f}s of {r['duration']:.0f}s")
json.dump(out,open(OUT,'w'),ensure_ascii=False,indent=1)
print(f"\n{len(out)} files, {tot} spans, {totd:.0f}s to beep "
      f"({100*totd/sum(v['duration'] for v in out.values()):.1f}% of audio)")
