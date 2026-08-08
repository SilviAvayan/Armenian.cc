#!/usr/bin/env python3
"""Validate the LLM judge against human gold BEFORE trusting it.
Reports 3-way agreement, binary (error vs not) agreement, and Cohen's kappa.
A judge is only worth scaling to the full corpus if it agrees with the human."""
import json, pathlib, argparse
from collections import Counter

HERE = pathlib.Path(__file__).resolve().parent.parent
ap=argparse.ArgumentParser()
ap.add_argument("--labels", default=str(HERE/"out"/"gold_labels.json"))
ap.add_argument("--judge-model", default="deepseek/deepseek-chat-v3.1")
args=ap.parse_args()

gold=json.loads((HERE/"out"/"gold_items.json").read_text())
cache=json.loads((HERE/"out"/"llm_cache.json").read_text())
L=json.loads(pathlib.Path(args.labels).read_text()); labels=L.get("labels",L)

def kappa(a,b):
    n=len(a); cats=sorted(set(a)|set(b))
    po=sum(1 for x,y in zip(a,b) if x==y)/n
    pe=sum((a.count(c)/n)*(b.count(c)/n) for c in cats)
    return (po-pe)/(1-pe) if pe<1 else 1.0, po

pairs=[]
for it in gold["words"]:
    wid=it["id"]; h=labels.get(wid)
    if not h or h.get("verdict") in (None,"unsure"): continue
    jc=cache.get(f"judge::{args.judge_model}::{wid}")
    if not jc: continue
    hv=h["verdict"]; jv=jc.get("verdict")
    if jv not in ("correct","acceptable","wrong"): continue
    pairs.append((hv,jv))

if not pairs:
    raise SystemExit("no overlapping (human, judge) pairs — run run_llm.py judge with a real key first")

h3=[p[0] for p in pairs]; j3=[p[1] for p in pairs]
# binary: is it a clear error?
def bin_(v): return "err" if v=="wrong" else "ok"
hb=[bin_(x) for x in h3]; jb=[bin_(x) for x in j3]
k3,po3=kappa(h3,j3); kb,pob=kappa(hb,jb)

conf=Counter((h,j) for h,j in zip(hb,jb))
tp=conf[("err","err")]; fp=conf[("ok","err")]
fn=conf[("err","ok")]; tn=conf[("ok","ok")]
prec=tp/(tp+fp) if tp+fp else None
rec=tp/(tp+fn) if tp+fn else None

out={"judge_model":args.judge_model,"n_pairs":len(pairs),
     "agreement_3way":round(po3,3),"kappa_3way":round(k3,3),
     "agreement_binary_err":round(pob,3),"kappa_binary_err":round(kb,3),
     "error_detection":{"tp":tp,"fp":fp,"fn":fn,"tn":tn,
        "precision":round(prec,3) if prec else None,
        "recall":round(rec,3) if rec else None},
     "verdict_trustworthy": kb>=0.4}
(HERE/"out"/"judge_validation.json").write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(json.dumps(out,ensure_ascii=False,indent=2))
print("\ninterpretation: kappa<0.2 poor, 0.2-0.4 fair, 0.4-0.6 moderate, 0.6-0.8 substantial")
