#!/usr/bin/env python3
"""Sample the model's linguistic NOTES for correctness annotation, stratified by
claim type so we cover derivation/contraction, grammar parses, and register."""
import json, pathlib, re, random, argparse
from collections import defaultdict
HERE=pathlib.Path(__file__).resolve().parent.parent
corpus=json.loads((HERE/"data"/"corpus.json").read_text())
VIDEOS={v["id"]:v for v in json.loads((HERE/"data"/"videos.json").read_text())}
ap=argparse.ArgumentParser(); ap.add_argument("--n",type=int,default=50)
ap.add_argument("--seed",type=int,default=20260808); a=ap.parse_args()
rng=random.Random(a.seed)

def claim_type(note):
    t=(note or "").lower()
    if re.search(r"сокращени|уменьшительн| от [ա-ֆ]|корн|суффикс|приставк|образова|буквальн",t):
        return "derivation"
    if re.search(r"накл|\bл\.\b|лицо|времен|прич|глагол|падеж|числ|спряжени|вспомог|связк|повелит|сослагат|будущ|прош|настоящ|дееприч",t):
        return "grammar"
    if re.search(r"разг|сленг|диалект|просторечи|вульгар|жаргон|фамильярн|груб",t):
        return "register"
    return "other"

cand=defaultdict(list)
for s in corpus:
    v=VIDEOS.get(s["video_id"],{})
    for n in s.get("notes",[]):
        note=n.get("note")
        if not note or not n.get("word"): continue
        cand[claim_type(note)].append({
            "video_id":s["video_id"],"handle":s.get("handle"),
            "url":v.get("url"),"src":v.get("src"),
            "seg_text":s.get("text",""),"seg_translation":s.get("explanation",""),
            "start":s.get("start"),"end":s.get("end"),
            "word":n["word"],"gloss":n.get("gloss"),"note":note,
            "claim_type":claim_type(note)})

# target mix across types, spread across videos (<=2 per video)
targets={"grammar":20,"derivation":15,"register":10,"other":5}
pick=[]; per_vid=defaultdict(int)
for typ,k in targets.items():
    pool=cand.get(typ,[]); rng.shuffle(pool); taken=0
    for it in pool:
        if per_vid[it["video_id"]]>=2: continue
        pick.append(it); per_vid[it["video_id"]]+=1; taken+=1
        if taken>=k: break
# top up to n if some types were short
allpool=[it for lst in cand.values() for it in lst]; rng.shuffle(allpool)
seen={(p["video_id"],p["word"],p["note"]) for p in pick}
for it in allpool:
    if len(pick)>=a.n: break
    key=(it["video_id"],it["word"],it["note"])
    if key in seen or per_vid[it["video_id"]]>=2: continue
    pick.append(it); seen.add(key); per_vid[it["video_id"]]+=1
pick=pick[:a.n]
for i,it in enumerate(pick): it["id"]=f"n{i:03d}"
(HERE/"out"/"note_items.json").write_text(json.dumps(pick,ensure_ascii=False,indent=2))
from collections import Counter
print("note sample:",dict(Counter(p["claim_type"] for p in pick)),f"= {len(pick)} -> out/note_items.json")
print(f"(of {sum(len(v) for v in cand.values())} total notes in corpus)")
