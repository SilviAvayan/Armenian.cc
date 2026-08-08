#!/usr/bin/env python3
"""Rebuild dataset/transcripts/google_chirp_3.basic from ~/Downloads/chirp_results.json.
ASCII-only: Armenian override texts are base64-encoded. Run from the repo root."""
import json, re, collections, base64
from pathlib import Path

OVERRIDES_B64 = {
  "multi_speakers__simpo.....samo_7629307328130501904": "1YrabmVyZWssIGR1a3Eg",
  "multi_speakers__zhanna_jaan_7668233361306995988": "1Ykg1a/VuiDVsSDVtA=="
}

OVERRIDES = {k: base64.b64decode(v).decode("utf-8") for k, v in OVERRIDES_B64.items()}

def degenerate(t, dur):
    letters = re.findall(u"[A-Za-z\u0400-\u04FF\u0530-\u058F\u0600-\u06FF\u0900-\u097F]", t)
    if len(letters) >= 5:
        arm = sum(1 for c in letters if u"\u0530" <= c <= u"\u058F")
        if arm / len(letters) < 0.5:
            return "wrong script"
    w = t.split()
    if dur > 3 and len(w) / dur > 6.0:
        return "impossible rate"
    if len(w) >= 20:
        g = collections.Counter(tuple(w[i:i+5]) for i in range(len(w)-4))
        c = g.most_common(1)[0][1]
        if c >= 15 and c*5/len(w) > 0.6:
            return "loop"
    return None

src = Path.home()/"Downloads"/"chirp_results.json"
d = json.loads(src.read_text(encoding="utf-8"))
ROOT = Path("dataset/transcripts/google_chirp_3.basic")
n = 0
for k, v in d.items():
    cat, clip, dur = v["category"], v["clip"], v["duration"]
    chunks = []
    parts = []
    for s in v["segments"]:
        t = (s.get("text") or "").strip()
        if t and degenerate(t, s.get("seg_duration",0)):
            t = ""
        if t: parts.append(t)
        chunks.append({"index":s["index"],"offset":s["offset"],"text":t,
            "usage":{"audio_seconds":s.get("audio_seconds"),"cost":s.get("cost")},
            "latency_seconds":s.get("latency"),"variant":s.get("variant"),
            "provider_model":"google/chirp-3"})
    text = " ".join(parts).strip()
    p = ROOT/cat; p.mkdir(parents=True, exist_ok=True)
    (p/(clip+".txt")).write_text(text+"\n", encoding="utf-8")
    payload = {"source":clip+".mp4","model":"google/chirp-3","requested_language":"hy",
        "endpoint":"openrouter /v1/audio/transcriptions",
        "method":"silence-aligned chunking <=51s + fallback ladder (wav-first) + quality gates (loop/rate/script)",
        "duration_seconds":dur,"ok":bool(text),"text":text,"chunks":chunks}
    if not text:
        payload["note"] = "model returned empty/degenerate output on every attempt (music-heavy or refused clip)"
    (p/(clip+".json")).write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",
                                  encoding="utf-8")
    n += 1
print("rebuilt %d clips under %s" % (n, ROOT))
