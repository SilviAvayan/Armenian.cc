#!/usr/bin/env python3
"""Sample segments for transcription ground-truth, stratified by the team's
difficulty categories so WER can be reported per difficulty (not just overall)."""
import json, pathlib, random, argparse
from collections import defaultdict
from difficulty import video_to_category, ORDER

HERE=pathlib.Path(__file__).resolve().parent.parent
corpus=json.loads((HERE/"data"/"corpus.json").read_text())
VIDEOS={v["id"]:v for v in json.loads((HERE/"data"/"videos.json").read_text())}
v2c=video_to_category()

ap=argparse.ArgumentParser()
ap.add_argument("--per-cat", type=int, default=5, help="segments per difficulty category")
ap.add_argument("--min-words", type=int, default=4)
ap.add_argument("--max-per-video", type=int, default=2)
ap.add_argument("--seed", type=int, default=20260808)
a=ap.parse_args()
rng=random.Random(a.seed)

# gather candidate segments per category
cand=defaultdict(list)
for s in corpus:
    c=v2c.get(s["video_id"])
    if not c: continue
    if not s.get("text") or len(s.get("words",[]))<a.min_words: continue
    cand[c].append(s)

pick=[]
for c in ORDER:
    segs=cand.get(c,[])
    rng.shuffle(segs)
    per_vid=defaultdict(int); taken=0
    for s in segs:
        if per_vid[s["video_id"]]>=a.max_per_video: continue
        v=VIDEOS.get(s["video_id"],{})
        pick.append({"category":c,"video_id":s["video_id"],"handle":s.get("handle"),
            "url":v.get("url"),"src":v.get("src"),"seg_index":s["seg_index"],
            "text":s["text"],"start":s.get("start"),"end":s.get("end")})
        per_vid[s["video_id"]]+=1; taken+=1
        if taken>=a.per_cat: break

for i,s in enumerate(pick): s["id"]=f"a{i:03d}"
(HERE/"out"/"asr_items.json").write_text(json.dumps(pick,ensure_ascii=False,indent=2))
from collections import Counter
print("ASR ground-truth sample:", dict(Counter(s["category"] for s in pick)),
      f"= {len(pick)} clips -> out/asr_items.json")
