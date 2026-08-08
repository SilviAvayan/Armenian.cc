#!/usr/bin/env python3
"""Run the reproduction translator (translate.py logic) on the gold segments and
evaluate it against the incumbent + the human gold — no new human labels needed.

Word gloss:  reproduction vs incumbent agreement; reproduction vs human gold via
             the (imperfect, κ=0.22) match-judge — reported WITH that caveat; plus
             fix-rate on incumbent-wrong words and preservation on incumbent-correct.
Sentence:    chrF++ of the reproduction translation vs the human reference — now a
             REAL measurement, because the reproduction is independent of the ref.
"""
import json, pathlib, re, threading, argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import llm_tasks as T
from chrf import chrf_pp

HERE=pathlib.Path(__file__).resolve().parent.parent; O=HERE/"out"
ap=argparse.ArgumentParser()
ap.add_argument("--tr-model", default="google/gemini-2.5-flash")
ap.add_argument("--match-model", default="deepseek/deepseek-chat-v3.1")
ap.add_argument("--workers", type=int, default=6)
a=ap.parse_args()

gi=json.loads((O/"gold_items.json").read_text())
gl=json.loads((O/"gold_labels.json").read_text()); gl=gl.get("labels",gl)
corpus={(s["video_id"],s["seg_index"]):s for s in json.loads((HERE/"data"/"corpus.json").read_text())}
norm=lambda t:re.sub(r"[։՝՜՞,.\s]+","",(t or "")).strip().lower()

# --- 1. translate the needed segments (reproduction) ---
need={}
for w in gi["words"]:
    need[(w["video_id"],w["seg_index"])]=1
for p in gi["phrases"]:
    need[(p["video_id"],p["seg_index"])]=1
segs=[corpus[k] for k in need if k in corpus]

TR_CACHE=O/"reproduction_cache.json"; tr=json.loads(TR_CACHE.read_text()) if TR_CACHE.exists() else {}
lock=threading.Lock()
def tkey(s): return f"{a.tr_model}::{s['video_id']}::{s['seg_index']}"
def translate(s):
    k=tkey(s)
    with lock:
        if k in tr: return tr[k]
    toks=[w["text"] for w in s.get("words",[])]
    r=T.translate_segment(a.tr_model, s["text"], toks, target="Russian")
    with lock: tr[k]=r; TR_CACHE.write_text(json.dumps(tr,ensure_ascii=False,indent=2))
    return r
print(f"translating {len(segs)} gold segments with {a.tr_model} …")
with ThreadPoolExecutor(max_workers=a.workers) as ex:
    futs=[ex.submit(translate,s) for s in segs]; done=0
    for f in as_completed(futs):
        done+=1
        if done%20==0: print(f"  {done}/{len(segs)}")

def repro_for(vid,si):
    return tr.get(f"{a.tr_model}::{vid}::{si}")

# --- 2. word-gloss eval ---
MCACHE=O/"reproduction_match_cache.json"; mc=json.loads(MCACHE.read_text()) if MCACHE.exists() else {}
def match(seg,word,gold,cand,key):
    with lock:
        if key in mc: return mc[key]
    if not cand: return False
    r=T.glosses_match(a.match_model,seg,word,gold,cand); v=bool(r.get("match"))
    with lock: mc[key]=v; MCACHE.write_text(json.dumps(mc,ensure_ascii=False,indent=2))
    return v

def gold_meaning(w,h):
    if h.get("verdict")=="correct": return w["gloss"]
    return (h.get("correction") or "").strip() or w["gloss"]

rows=[]; jobs=[]
for w in gi["words"]:
    h=gl.get(w["id"],{})
    if h.get("verdict") in (None,"unsure"): continue
    r=repro_for(w["video_id"],w["seg_index"])
    if not r: continue
    glosses=r.get("glosses") or []
    wi=w.get("word_index")
    rg=glosses[wi] if isinstance(wi,int) and 0<=wi<len(glosses) else None
    rows.append({"id":w["id"],"stratum":w["stratum"],"word":w["word"],
        "incumbent":w["gloss"],"repro":rg,"human_verdict":h["verdict"],
        "gold":gold_meaning(w,h),"seg":w["seg_text"]})

# match-judge reproduction vs gold (threaded)
def do_match(x): return x["id"], match(x["seg"],x["word"],x["gold"],x["repro"],f"repro::{x['id']}")
with ThreadPoolExecutor(max_workers=a.workers) as ex:
    for wid,ok in ex.map(do_match, rows):
        next(r for r in rows if r["id"]==wid)["repro_match"]=ok

for r in rows:
    r["agree_incumbent"]= (norm(r["repro"])==norm(r["incumbent"])) if r["repro"] else False

N=len(rows)
repro_acc=sum(1 for r in rows if r.get("repro_match"))/N if N else 0
agree=sum(1 for r in rows if r["agree_incumbent"])/N if N else 0
inc_wrong=[r for r in rows if r["human_verdict"] in ("wrong","acceptable")]
inc_right=[r for r in rows if r["human_verdict"]=="correct"]
fix_rate=sum(1 for r in inc_wrong if r.get("repro_match"))/len(inc_wrong) if inc_wrong else None
preserve=sum(1 for r in inc_right if r.get("repro_match"))/len(inc_right) if inc_right else None

# --- 3. sentence eval: reproduction vs human reference (chrF++) ---
sr=json.loads((O/"sentence_refs.json").read_text()).get("sentences",{}) if (O/"sentence_refs.json").exists() else {}
sent=[]
for p in gi["phrases"]:
    ref=(sr.get(p["id"],{}).get("reference") or "").strip()
    r=repro_for(p["video_id"],p["seg_index"])
    if not ref or not r: continue
    repro_tr=r.get("sentence","")
    sent.append({"id":p["id"],"chrfpp_repro":round(chrf_pp(repro_tr,ref),1),
        "chrfpp_incumbent":round(chrf_pp(p["explanation"],ref),1)})
sent_repro=round(sum(s["chrfpp_repro"] for s in sent)/len(sent),1) if sent else None
sent_inc=round(sum(s["chrfpp_incumbent"] for s in sent)/len(sent),1) if sent else None

out={"tr_model":a.tr_model,"match_model":a.match_model,
     "n_words":N,
     "reproduction_gloss_acc_vs_gold":round(repro_acc,3),
     "agreement_with_incumbent":round(agree,3),
     "fix_rate_on_incumbent_errors":None if fix_rate is None else round(fix_rate,3),
     "preservation_on_incumbent_correct":None if preserve is None else round(preserve,3),
     "n_incumbent_wrong":len(inc_wrong),"n_incumbent_correct":len(inc_right),
     "sentence_chrfpp_reproduction":sent_repro,"sentence_chrfpp_incumbent":sent_inc,
     "n_sentences":len(sent),
     "caveat":"gloss-vs-gold scored by match-judge (κ=0.22 vs human) — directional only; "
              "agreement_with_incumbent + sentence chrF++ are the robust numbers.",
     "rows":rows,"sentences":sent}
(O/"reproduction_eval.json").write_text(json.dumps(out,ensure_ascii=False,indent=2))
print("\n=== REPRODUCTION EVAL ===")
for k in ("n_words","reproduction_gloss_acc_vs_gold","agreement_with_incumbent",
          "fix_rate_on_incumbent_errors","preservation_on_incumbent_correct",
          "sentence_chrfpp_reproduction","sentence_chrfpp_incumbent","n_sentences"):
    print(f"  {k}: {out[k]}")
print("wrote out/reproduction_eval.json")
