#!/usr/bin/env python3
"""Bridge: ElevenLabs Scribe word-level output -> eval-ready segments.

ElevenLabs Scribe returns a `words` list where each word has text/start/end/
logprob (and type/speaker_id). This groups those words into sentence segments
(split on Armenian/Latin sentence punctuation, big time gaps, or speaker change)
and emits the SCHEMA.md shape WITHOUT translations — i.e. exactly what the
translate.py stage consumes.

Input: a JSON file that is either
  {"words":[{"text","start","end","logprob","type","speaker_id"}, ...]}   (raw Scribe)
  or just a list of such word dicts.

Usage: python3 scripts/asr_to_segments.py scribe_result.json -o out/asr_segments.json
"""
import json, argparse, pathlib, re

SENT_END = tuple("։?!.…")   # Armenian full stop ։ + Latin
GAP = 0.8                    # seconds of silence that also ends a segment

def load_words(path):
    d = json.loads(pathlib.Path(path).read_text())
    words = d["words"] if isinstance(d, dict) and "words" in d else d
    out = []
    for w in words:
        # skip non-speech tokens (audio events, spacing) but keep punctuation on words
        if w.get("type") not in (None, "word", "spacing", "punctuation"):
            continue
        if w.get("type") == "spacing":
            continue
        t = (w.get("text") or "").strip()
        if not t:
            continue
        out.append({"text": t, "start": w.get("start"), "end": w.get("end"),
                    "logprob": w.get("logprob"), "speaker": w.get("speaker_id")})
    return out

def segment(words):
    segs, cur = [], []
    for i, w in enumerate(words):
        if cur:
            prev = cur[-1]
            gap = (w["start"] or 0) - (prev["end"] or 0) if (w.get("start") is not None and prev.get("end") is not None) else 0
            if w.get("speaker") != prev.get("speaker") or gap >= GAP:
                segs.append(cur); cur = []
        cur.append(w)
        if w["text"].endswith(SENT_END):
            segs.append(cur); cur = []
    if cur: segs.append(cur)
    out = []
    for s in segs:
        text = re.sub(r"\s+([։?!.,…])", r"\1", " ".join(w["text"] for w in s)).strip()
        out.append({
            "start": s[0].get("start"), "end": s[-1].get("end"), "text": text,
            "words": [{"text":w["text"],"start":w["start"],"end":w["end"],
                       "logprob":w["logprob"]} for w in s],
        })
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scribe_json")
    ap.add_argument("-o","--out", default="out/asr_segments.json")
    a = ap.parse_args()
    words = load_words(a.scribe_json)
    segs = segment(words)
    pathlib.Path(a.out).write_text(json.dumps(segs, ensure_ascii=False, indent=2))
    nlp = sum(1 for s in segs for w in s["words"] if isinstance(w["logprob"],(int,float)))
    nw = sum(len(s["words"]) for s in segs)
    print(f"{len(words)} words -> {len(segs)} segments  ({nlp}/{nw} words carry logprob)")
    print(f"wrote {a.out}  (feed to: python3 scripts/translate.py --in {a.out})")

if __name__ == "__main__":
    main()
