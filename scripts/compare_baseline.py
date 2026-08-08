#!/usr/bin/env python3
"""'Does the LLM earn its place?' — controlled experiment.

For every gold word we have three glosses of the SAME word:
  * production  : armenian.cc's shipped gloss (Gemini, with context)
  * ctx         : re-glossed WITH context (baseline arm, same model)
  * noctx       : glossed WITHOUT context — the dictionary-style lookup
We score each against the human GOLD meaning using a semantic-match judge, then
compare accuracy per stratum. If noctx collapses on colloquial/polysemy strata
but ctx holds, context (hence an LLM that reads it) is doing real work — a plain
dictionary/form would not. Match calls are cached in out/llm_cache.json.
"""
import json, pathlib, argparse
import llm_tasks as T

HERE=pathlib.Path(__file__).resolve().parent.parent
ap=argparse.ArgumentParser()
ap.add_argument("--labels", default=str(HERE/"out"/"gold_labels.json"))
ap.add_argument("--system-model", default="deepseek/deepseek-chat-v3.1")
ap.add_argument("--match-model", default="deepseek/deepseek-chat-v3.1")
args=ap.parse_args()

gold=json.loads((HERE/"out"/"gold_items.json").read_text())
cache=json.loads((HERE/"out"/"llm_cache.json").read_text())
CACHE=HERE/"out"/"llm_cache.json"
L=json.loads(pathlib.Path(args.labels).read_text()); labels=L.get("labels",L)

def gold_gloss(it, h):
    """Human-derived correct meaning for this word in context."""
    if h["verdict"]=="correct": return it["gloss"]
    c=(h.get("correction") or "").strip()
    return c or None

def match(seg,word,g,cand,key):
    if key in cache: return cache[key]["match"]
    r=T.glosses_match(args.match_model,seg,word,g,cand)
    cache[key]=r; CACHE.write_text(json.dumps(cache,ensure_ascii=False,indent=2))
    return r["match"]

from collections import defaultdict
agg=defaultdict(lambda:{"prod":[0,0],"ctx":[0,0],"noctx":[0,0]})
rows=[]
for it in gold["words"]:
    wid=it["id"]; h=labels.get(wid)
    if not h or h.get("verdict") in (None,"unsure"): continue
    g=gold_gloss(it,h)
    if not g: continue                      # no ground-truth meaning to score against
    seg,word=it["seg_text"],it["word"]
    prod=it["gloss"]
    ctx=(cache.get(f"ctx::{args.system_model}::{wid}") or {}).get("gloss")
    noctx=(cache.get(f"noctx::{args.system_model}::{wid}") or {}).get("gloss")
    if ctx is None or noctx is None:
        continue
    mp=match(seg,word,g,prod,f"match::prod::{wid}")
    mc=match(seg,word,g,ctx,f"match::ctx::{wid}")
    mn=match(seg,word,g,noctx,f"match::noctx::{wid}")
    s=it["stratum"]
    for name,ok in (("prod",mp),("ctx",mc),("noctx",mn)):
        agg[s][name][0]+=int(ok); agg[s][name][1]+=1
        agg["ALL"][name][0]+=int(ok); agg["ALL"][name][1]+=1
    rows.append({"id":wid,"stratum":s,"word":word,"gold":g,
                 "prod":prod,"ctx":ctx,"noctx":noctx,
                 "prod_ok":mp,"ctx_ok":mc,"noctx_ok":mn})

def acc(pair): return round(pair[0]/pair[1],3) if pair[1] else None
table={s:{k:acc(v) for k,v in d.items()} | {"n":d["prod"][1]} for s,d in agg.items()}
out={"system_model":args.system_model,"per_stratum":table,"rows":rows}
(HERE/"out"/"baseline.json").write_text(json.dumps(out,ensure_ascii=False,indent=2))

print(f"{'stratum':22s} {'n':>3} {'prod':>6} {'ctx':>6} {'noctx':>6}  Δ(ctx-noctx)")
for s in sorted(table):
    t=table[s]
    d = (t['ctx']-t['noctx']) if (t['ctx'] and t['noctx'] is not None) else None
    print(f"{s:22s} {t['n']:>3} {str(t['prod']):>6} {str(t['ctx']):>6} "
          f"{str(t['noctx']):>6}  {round(d,3) if d is not None else '—'}")
print("\nwrote out/baseline.json")
