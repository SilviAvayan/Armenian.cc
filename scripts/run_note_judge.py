#!/usr/bin/env python3
"""Grammar/note judge (Move 3).
  --mode validate : judge the 50 annotated notes, report agreement + Cohen's kappa vs human.
  --mode scale    : judge ALL corpus notes, report correctness rate overall + by claim type.
  --mode both     : validate, then (if trustworthy) scale.
Cross-family judge (default DeepSeek, not the Gemini being judged). MOCK=1 to dry-run.
"""
import json, os, pathlib, argparse, threading, sys, re
from concurrent.futures import ThreadPoolExecutor, as_completed
import llm_tasks as T

def claim_type(note):
    t=(note or "").lower()
    if re.search(r"сокращени|уменьшительн| от [ա-ֆ]|корн|суффикс|приставк|образова|буквальн",t): return "derivation"
    if re.search(r"накл|\bл\.\b|лицо|времен|прич|глагол|падеж|числ|спряжени|вспомог|связк|повелит|сослагат|будущ|прош|настоящ|дееприч",t): return "grammar"
    if re.search(r"разг|сленг|диалект|просторечи|вульгар|жаргон|фамильярн|груб",t): return "register"
    return "other"

HERE=pathlib.Path(__file__).resolve().parent.parent; O=HERE/"out"
ap=argparse.ArgumentParser()
ap.add_argument("--mode",choices=["validate","scale","both"],default="both")
ap.add_argument("--model",default="deepseek/deepseek-chat-v3.1")
ap.add_argument("--labels",default=str(O/"note_labels.json"))
ap.add_argument("--workers",type=int,default=6)
a=ap.parse_args()
CACHE=O/"note_judge_cache.json"; cache=json.loads(CACHE.read_text()) if CACHE.exists() else {}
lock=threading.Lock()
import hashlib
def jkey(seg,word,note): return f"{a.model}::"+hashlib.md5(f"{seg}|{word}|{note}".encode()).hexdigest()
def judge(seg,word,gloss,note):
    k=jkey(seg,word,note)
    with lock:
        if k in cache: return cache[k]
    v=T.judge_note(a.model,seg,word,gloss,note)
    with lock: cache[k]=v; CACHE.write_text(json.dumps(cache,ensure_ascii=False,indent=2))
    return v

def run(items):
    out={}
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        fut={ex.submit(judge,it["seg_text"],it["word"],it.get("gloss"),it["note"]):it for it in items}
        done=0
        for f in as_completed(fut):
            it=fut[f]
            try: out[it["id"]]=f.result()
            except Exception as e:
                if done<3: print("  err",e,file=sys.stderr)
            done+=1
            if done%25==0: print(f"  {done}/{len(items)}")
    return out

def kappa(a_,b_):
    n=len(a_); cats=sorted(set(a_)|set(b_))
    po=sum(x==y for x,y in zip(a_,b_))/n
    pe=sum((a_.count(c)/n)*(b_.count(c)/n) for c in cats)
    return (po-pe)/(1-pe) if pe<1 else 1.0, po

def validate():
    items=json.loads((O/"note_items.json").read_text())
    lp=pathlib.Path(a.labels)
    if not lp.exists(): raise SystemExit(f"no human note labels at {lp}")
    H=json.loads(lp.read_text()); H=H.get("labels",H)
    jr=run(items)
    pairs=[]
    for it in items:
        h=H.get(it["id"],{}).get("verdict"); j=jr.get(it["id"],{}).get("verdict")
        if h in (None,"unsure") or j not in ("correct","partial","wrong"): continue
        pairs.append((h,j))
    if not pairs: raise SystemExit("no overlapping labeled/judged notes")
    # binary: correct vs not
    hb=["ok" if h=="correct" else "bad" for h,_ in pairs]
    jb=["ok" if j=="correct" else "bad" for _,j in pairs]
    kb,pob=kappa(hb,jb)
    k3,po3=kappa([h for h,_ in pairs],[j for _,j in pairs])
    res={"n_pairs":len(pairs),"agreement_binary":round(pob,3),"kappa_binary":round(kb,3),
         "agreement_3way":round(po3,3),"kappa_3way":round(k3,3),
         "trustworthy":kb>=0.4,"judge_model":a.model}
    (O/"note_judge_validation.json").write_text(json.dumps(res,ensure_ascii=False,indent=2))
    print("VALIDATION:",json.dumps(res,ensure_ascii=False))
    return res

def scale():
    corpus=json.loads((HERE/"data"/"corpus.json").read_text())
    notes=[]
    for s in corpus:
        for n in s.get("notes",[]):
            if n.get("note") and n.get("word"):
                notes.append({"id":f"{s['video_id']}#{s['seg_index']}#{n['word']}",
                    "seg_text":s.get("text",""),"word":n["word"],"gloss":n.get("gloss"),
                    "note":n["note"],"claim_type":claim_type(n["note"])})
    jr=run(notes)
    from collections import Counter,defaultdict
    by=defaultdict(lambda:Counter())
    allc=Counter()
    for it in notes:
        v=jr.get(it["id"],{}).get("verdict")
        if not v: continue
        by[it["claim_type"]][v]+=1; allc[v]+=1
    tot=sum(allc.values())
    def rate(c):
        t=sum(c.values()); return round(c.get("correct",0)/t,3) if t else None
    res={"n_judged":tot,"correct_rate_overall":rate(allc),
         "by_claim_type":{k:{"n":sum(v.values()),"correct_rate":rate(v),"dist":dict(v)} for k,v in by.items()}}
    (O/"note_judge_corpus.json").write_text(json.dumps(res,ensure_ascii=False,indent=2))
    print("SCALE:",json.dumps(res,ensure_ascii=False,indent=2))
    return res

if __name__=="__main__":
    if a.mode in ("validate","both"):
        v=validate()
        if a.mode=="both" and not v["trustworthy"]:
            print("judge not trustworthy (kappa<0.4) — skipping scale; human stays in loop.")
            sys.exit(0)
    if a.mode in ("scale","both"):
        scale()
