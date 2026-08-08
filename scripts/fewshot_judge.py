#!/usr/bin/env python3
"""Task B.1 — can few-shot make the gloss judge trustworthy?
Seed the judge with a handful of the human-labeled examples (correct + wrong,
with the human's reason), then re-judge the REST of the gold and re-measure
Cohen's kappa vs human. Exemplars are held out of the evaluation (no leakage)."""
import json, pathlib, argparse, threading, re
from concurrent.futures import ThreadPoolExecutor
import orclient

HERE=pathlib.Path(__file__).resolve().parent.parent; O=HERE/"out"
ap=argparse.ArgumentParser()
ap.add_argument("--judge-model", default="deepseek/deepseek-chat-v3.1")
ap.add_argument("--shots", type=int, default=8)
ap.add_argument("--workers", type=int, default=6)
a=ap.parse_args()

gi={w["id"]:w for w in json.loads((O/"gold_items.json").read_text())["words"]}
gl=json.loads((O/"gold_labels.json").read_text()); gl=gl.get("labels",gl)
rows=[{"id":wid,"seg":gi[wid]["seg_text"],"word":gi[wid]["word"],"gloss":gi[wid]["gloss"],
       "human":h["verdict"],"corr":(h.get("correction") or "").strip()}
      for wid,h in gl.items() if wid in gi and h.get("verdict") in ("correct","acceptable","wrong")]

# pick balanced exemplars (some correct, some wrong), stratified, deterministic
wrong=[r for r in rows if r["human"]=="wrong"]; correct=[r for r in rows if r["human"]=="correct"]
shots = wrong[:a.shots//2] + correct[:a.shots-len(wrong[:a.shots//2])]
shot_ids={r["id"] for r in shots}
evalr=[r for r in rows if r["id"] not in shot_ids]

def shot_block(r):
    verd = "correct" if r["human"]=="correct" else ("acceptable" if r["human"]=="acceptable" else "wrong")
    return (f'Phrase: «{r["seg"]}»\nWord: «{r["word"]}»  Gloss: «{r["gloss"]}»\n'
            f'→ {{"verdict":"{verd}","correct_gloss":"{r["corr"] or r["gloss"]}"}}')
FEWSHOT="\n\n".join(shot_block(r) for r in shots)

SYS=("You are a bilingual Armenian–Russian linguist grading a language-learning app's "
     "per-word Russian glosses. Match the calibration of these expert-labeled examples "
     "(colloquial/spoken Armenian; judge the word AS USED IN CONTEXT):\n\n"+FEWSHOT)
TMPL=('Phrase: «{seg}»\nWord: «{word}»\nApp gloss: «{gloss}»\n'
      'Is the gloss correct for the word AS USED HERE? '
      'Reply ONLY JSON: {{"verdict":"correct|acceptable|wrong"}}')

lock=threading.Lock(); CACHE=O/"fewshot_judge_cache.json"
cache=json.loads(CACHE.read_text()) if CACHE.exists() else {}
def judge(r):
    k=f'{a.judge_model}::fs{a.shots}::{r["id"]}'
    with lock:
        if k in cache: return r["id"],cache[k]
    out=orclient.chat(a.judge_model,[{"role":"system","content":SYS},
        {"role":"user","content":TMPL.format(seg=r["seg"],word=r["word"],gloss=r["gloss"])}],
        temperature=0.0,max_tokens=1200,json_mode=True,reasoning={"effort":"low"})
    try: v=json.loads(re.search(r"\{.*\}",out,re.S).group(0)).get("verdict")
    except Exception: v=None
    with lock: cache[k]=v; CACHE.write_text(json.dumps(cache,ensure_ascii=False))
    return r["id"],v

with ThreadPoolExecutor(max_workers=a.workers) as ex:
    jv=dict(ex.map(judge, evalr))

# binary: correct vs not
def kappa(hh,jj):
    n=len(hh); cats=sorted(set(hh)|set(jj))
    po=sum(x==y for x,y in zip(hh,jj))/n
    pe=sum((hh.count(c)/n)*(jj.count(c)/n) for c in cats)
    return (po-pe)/(1-pe) if pe<1 else 1.0, po
pairs=[(r["human"], jv[r["id"]]) for r in evalr if jv.get(r["id"]) in ("correct","acceptable","wrong")]
hb=["ok" if h=="correct" else "bad" for h,_ in pairs]
jb=["ok" if j=="correct" else "bad" for _,j in pairs]
kb,pob=kappa(hb,jb)
# error detection
tp=sum(1 for h,j in zip(hb,jb) if h=="bad" and j=="bad"); fp=sum(1 for h,j in zip(hb,jb) if h=="ok" and j=="bad")
fn=sum(1 for h,j in zip(hb,jb) if h=="bad" and j=="ok")
prec=tp/(tp+fp) if tp+fp else None; rec=tp/(tp+fn) if tp+fn else None
out={"judge_model":a.judge_model,"shots":a.shots,"n_eval":len(pairs),
     "agreement_binary":round(pob,3),"kappa_binary":round(kb,3),
     "error_precision":round(prec,3) if prec is not None else None,
     "error_recall":round(rec,3) if rec is not None else None,
     "vs_zeroshot_kappa":0.22,"trustworthy":kb>=0.4}
(O/"fewshot_judge.json").write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(json.dumps(out,ensure_ascii=False,indent=2))
