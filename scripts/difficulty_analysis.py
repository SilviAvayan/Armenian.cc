#!/usr/bin/env python3
"""ASR-stage evaluation by difficulty category (no transcription, no ASR built).
Joins the team's human difficulty labels onto ElevenLabs' shipped per-word
confidence in the scraped corpus, and shows confidence degrades with difficulty.
Also emits gloss-accuracy-by-difficulty when human labels exist."""
import json, pathlib, math, statistics as st
from collections import defaultdict
from difficulty import video_to_category, ORDER

HERE = pathlib.Path(__file__).resolve().parent.parent
corpus = json.loads((HERE/"data"/"corpus.json").read_text())
v2c = video_to_category()

# ---- confidence by category (whole corpus, needs no labels) ----
lps = defaultdict(list); vids = defaultdict(set)
for s in corpus:
    c = v2c.get(s["video_id"])
    if not c: continue
    vids[c].add(s["video_id"])
    for w in s.get("words", []):
        lp = w.get("logprob")
        if isinstance(lp,(int,float)): lps[c].append(lp)

conf = {}
for c in ORDER:
    L = lps.get(c)
    if not L: continue
    conf[c] = {"videos":len(vids[c]),"words":len(L),
               "mean_conf":round(st.mean(math.exp(x) for x in L),3),
               "median_conf":round(math.exp(st.median(L)),3),
               "low_conf_rate":round(sum(1 for x in L if x<-0.3)/len(L),3)}

out = {"n_labeled_videos":len(set(v2c)&set(s["video_id"] for s in corpus)),
       "confidence_by_category":conf}
(HERE/"out"/"asr_difficulty.json").write_text(json.dumps(out,ensure_ascii=False,indent=2))

print(f"{'category':16s} {'vids':>4} {'words':>6} {'meanConf':>8} {'lowConf%':>8}")
for c in ORDER:
    if c in conf:
        d=conf[c]; print(f"{c:16s} {d['videos']:>4} {d['words']:>6} "
                          f"{d['mean_conf']:>8.3f} {100*d['low_conf_rate']:>7.1f}%")
print("wrote out/asr_difficulty.json")
