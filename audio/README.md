# Audio de-identification

Beeping personal information out of call recordings. Same discipline as the git
tooling in the parent directory, different medium.

## Pipeline

| step | script |
|---|---|
| 1. transcribe with word-level timestamps | (any Whisper-family recogniser) |
| 2. **gate the transcript** | `check_transcript_quality.py` |
| 3. find spoken PII | `find_spoken_pii.py` |
| 4. beep it | `apply_beeps.py` |
| 5. verify on the FINISHED audio | `verify_beeped.py` |

Step 2 is not optional. See below.

## Four things that produce a confidently wrong result

### Filenames carry the phone number

Asterisk/FreePBX names recordings `IN-<queue>-<the other party's number>-<date>-<time>-<callid>.wav`.
On one 24-file set that was 22 distinct real phone numbers before a single second of
audio had been examined. Rename first; keep the mapping in a mode-600 file that never
travels with the audio.

### A degraded transcript reports CLEAN

Recognition worked on English and produced structurally broken text in Punjabi, Kannada
and Bengali — while reporting language confidence of 1.00 and a healthy words-per-minute
rate. The worst file scored **146 wpm**, higher than several correct ones.

Words per minute measures fluency, not correctness. What works, with no knowledge of the
language: script purity (Punjabi is written in Gurmukhi; drift into Bengali or Latin is
the model guessing), words mixing two scripts, invalid code points, and long segments
holding almost no words. `check_transcript_quality.py` applies all four.

A PII detector fed nonsense finds no names and no numbers and reports the file clean.

### Word timestamps are approximate; beeping to them leaks

A recogniser placed a phone number at 10.01s when the speaker began it at 8.0s. Beeping
the stated span left the area code audible. Padding is guesswork — instead extend each
span outward through the real audio until the level drops to silence, bounded by the
neighbouring transcript words. The word ORDER is reliable even when the TIME is not.

Do not extend on silence alone: without the word bound a span grows through a pause and
swallows ordinary speech (15% of one file).

### The verification must know how numbers are spoken

A first check looked for digits and names, and returned **zero survivors on a file that
was leaking** — because the leak was "seven one seven", a number read aloud as words.
`verify_beeped.py` covers digits, names and runs of number words.

Re-transcription also reports FALSE survivors: at a beep boundary the model completes the
sentence from context and emits a name that is not audible. Confirm acoustically (a
Goertzel test at the beep frequency, plus RMS) before treating a survivor as real.

## Configuration

`find_spoken_pii.py` and `verify_beeped.py` read a given-names list from
`$SPOKEN_PII_NAMES` (default `/etc/deid/given-names.txt`), one lowercase name per line.

**That file is not in this repo and must not be.** A list of the names you are removing
is itself the PII you are removing. Ship the tooling; keep the list beside your data.

Without it the structural rules still run — titles, naming cues, digit runs,
letter-by-letter spelling — which are the primary defence. The list is a net beneath them.

## What beeping does not do

It removes the sound, not the inference: a listener still hears the shape of the
conversation around the gap. And the voice itself is personal data, unchanged by any of
this — someone who knows a speaker can still recognise them.
