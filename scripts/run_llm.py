#!/usr/bin/env python3
"""Generate LLM outputs over the gold word items:
   - judge      : cross-family model grades each PRODUCTION gloss (for judge validation)
   - ctx        : same model re-glosses the word WITH context   (baseline arm 1)
   - noctx      : same model glosses the word WITHOUT context    (baseline arm 2)
Results cached to out/llm_cache.json so reruns are incremental. Set MOCK=1 to
dry-run with no network.

Usage:
  MOCK=1 python3 scripts/run_llm.py --tasks judge,ctx,noctx
  python3 scripts/run_llm.py --judge-model deepseek/deepseek-chat-v3.1 \
                             --system-model deepseek/deepseek-chat-v3.1
"""
import json, os, pathlib, argparse, threading, sys
from concurrent.futures import ThreadPoolExecutor, as_completed
import llm_tasks as T

HERE = pathlib.Path(__file__).resolve().parent.parent
gold = json.loads((HERE/"out"/"gold_items.json").read_text())
CACHE = HERE/"out"/"llm_cache.json"
cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
lock = threading.Lock()

ap = argparse.ArgumentParser()
ap.add_argument("--tasks", default="judge,ctx,noctx")
ap.add_argument("--judge-model", default="deepseek/deepseek-chat-v3.1")
ap.add_argument("--system-model", default="deepseek/deepseek-chat-v3.1")
ap.add_argument("--workers", type=int, default=6)
args = ap.parse_args()
TASKS = args.tasks.split(",")

def cget(k):
    with lock: return cache.get(k)
def cput(k,v):
    with lock:
        cache[k]=v
        CACHE.write_text(json.dumps(cache,ensure_ascii=False,indent=2))

def work(it):
    wid, seg, word, gloss = it["id"], it["seg_text"], it["word"], it["gloss"]
    res={}
    if "judge" in TASKS:
        k=f"judge::{args.judge_model}::{wid}"
        v=cget(k)
        if v is None:
            v=T.judge_gloss(args.judge_model, seg, word, gloss); cput(k,v)
        res["judge"]=v
    if "ctx" in TASKS:
        k=f"ctx::{args.system_model}::{wid}"
        v=cget(k)
        if v is None:
            v=T.gloss_in_context(args.system_model, seg, word); cput(k,v)
        res["ctx"]=v
    if "noctx" in TASKS:
        k=f"noctx::{args.system_model}::{wid}"
        v=cget(k)
        if v is None:
            v=T.gloss_no_context(args.system_model, word); cput(k,v)
        res["noctx"]=v
    return wid,res

def main():
    items=gold["words"]
    done=0; errs=0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs=[ex.submit(work,it) for it in items]
        for f in as_completed(futs):
            try:
                wid,_=f.result(); done+=1
            except Exception as e:
                errs+=1
                if errs<=3: print("  err:",e,file=sys.stderr)
            if done%20==0: print(f"  {done}/{len(items)}")
    print(f"done {done}/{len(items)} items  errors={errs}  "
          f"({'MOCK' if T.MOCK else args.judge_model})")
    print("cache:",CACHE)

if __name__=="__main__":
    main()
