#!/usr/bin/env python3
"""Translation-model bake-off: run several LLMs on the SAME gold + a broader
sample, score with deterministic chrF++ (sidesteps the κ=0.22 judge).

GOLD (130 words + 20 sentences, human-labeled) → ACCURACY:
  gloss chrF++ vs gold meaning · exact agreement · sentence chrF++ vs human ref
BROADER sample (no gold) → ROBUSTNESS + cost:
  empty/refusal rate · gloss-count mismatch · non-Cyrillic gloss rate ·
  chrF++ vs incumbent (closeness to production) · latency/call
"""
import json, pathlib, re, time, random, threading, argparse, hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
import llm_tasks as T
from chrf import chrf_pp

HERE=pathlib.Path(__file__).resolve().parent.parent; O=HERE/"out"
DEFAULT=["google/gemini-2.5-flash","google/gemini-2.5-flash-lite","google/gemini-2.5-pro",
         "deepseek/deepseek-chat-v3.1","openai/gpt-4o-mini","openai/gpt-4.1-mini",
         "anthropic/claude-3.5-haiku","anthropic/claude-3.7-sonnet"]
ap=argparse.ArgumentParser()
ap.add_argument("--models", default=",".join(DEFAULT))
ap.add_argument("--broader", type=int, default=120)
ap.add_argument("--workers", type=int, default=6)
ap.add_argument("--seed", type=int, default=20260808)
a=ap.parse_args()
MODELS=[m.strip() for m in a.models.split(",") if m.strip()]

gi=json.loads((O/"gold_items.json").read_text())
gl=json.loads((O/"gold_labels.json").read_text()); gl=gl.get("labels",gl)
sr=json.loads((O/"sentence_refs.json").read_text()).get("sentences",{}) if (O/"sentence_refs.json").exists() else {}
corpus_list=json.loads((HERE/"data"/"corpus.json").read_text())
corpus={(s["video_id"],s["seg_index"]):s for s in corpus_list}
norm=lambda t:re.sub(r"[։՝՜՞,.\s]+","",(t or "")).strip().lower()
def gold_meaning(w,h): return w["gloss"] if h.get("verdict")=="correct" else ((h.get("correction") or "").strip() or w["gloss"])

# broader sample: random corpus segments not among gold segments
goldsegs={(w["video_id"],w["seg_index"]) for w in gi["words"]}|{(p["video_id"],p["seg_index"]) for p in gi["phrases"]}
pool=[s for s in corpus_list if (s["video_id"],s["seg_index"]) not in goldsegs and s.get("explanation") and len(s.get("words",[]))>=3]
random.Random(a.seed).shuffle(pool); broader=pool[:a.broader]

CACHE=O/"bakeoff_cache.json"; cache=json.loads(CACHE.read_text()) if CACHE.exists() else {}
lock=threading.Lock()
def ck(model,text): return f"{model}::"+hashlib.md5(text.encode()).hexdigest()
def tr(model,seg):
    k=ck(model,seg["text"])
    with lock:
        if k in cache: return cache[k]
    toks=[w["text"] for w in seg.get("words",[])]
    t0=time.time()
    try: r=T.translate_segment(model, seg["text"], toks, target="Russian")
    except Exception as e: r={"_error":str(e)[:120],"glosses":[],"sentence":"","notes":[]}
    r["_lat"]=round(time.time()-t0,2)
    with lock: cache[k]=r; CACHE.write_text(json.dumps(cache,ensure_ascii=False,indent=2))
    return r

def probe(model):
    try:
        import orclient; orclient.chat(model,[{"role":"user","content":"ok"}],max_tokens=5); return True
    except Exception as e:
        print(f"  SKIP {model}: {str(e)[:80]}"); return False

def non_cyr(g): return bool(g) and not re.search(r"[А-Яа-яЁё]", g)

results={}
for model in MODELS:
    if not probe(model): continue
    print(f"— {model} —")
    segset={}
    allsegs={(w["video_id"],w["seg_index"]) for w in gi["words"] if gl.get(w["id"],{}).get("verdict") not in (None,"unsure")}
    allsegs|={(p["video_id"],p["seg_index"]) for p in gi["phrases"]}
    allsegs|={(s["video_id"],s["seg_index"]) for s in broader}
    segs=[corpus[k] for k in allsegs if k in corpus]
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        list(ex.map(lambda s: tr(model,s), segs))
    def R(s): return cache.get(ck(model,s["text"]),{})
    # gold gloss
    gch=[]; gag=[]
    for w in gi["words"]:
        h=gl.get(w["id"],{})
        if h.get("verdict") in (None,"unsure"): continue
        r=R(corpus[(w["video_id"],w["seg_index"])]); gls=r.get("glosses") or []
        wi=w.get("word_index"); cand=gls[wi] if isinstance(wi,int) and 0<=wi<len(gls) else None
        gm=gold_meaning(w,h)
        gch.append(chrf_pp(cand or "", gm)); gag.append(1 if cand and norm(cand)==norm(gm) else 0)
    # gold sentence
    sch=[]
    for p in gi["phrases"]:
        ref=(sr.get(p["id"],{}).get("reference") or "").strip()
        if not ref: continue
        r=R(corpus[(p["video_id"],p["seg_index"])]); sch.append(chrf_pp(r.get("sentence",""),ref))
    # broader robustness
    empty=mismatch=noncyr=0; lats=[]; inc_ch=[]
    for s in broader:
        r=R(s); gls=r.get("glosses") or []; lats.append(r.get("_lat",0))
        if r.get("_error") or not r.get("sentence"): empty+=1
        if len(gls)!=len(s["words"]): mismatch+=1
        noncyr+=sum(1 for g in gls if non_cyr(g));
        inc_ch.append(chrf_pp(r.get("sentence",""), s.get("explanation","")))
    tot_bw=sum(len(s["words"]) for s in broader) or 1
    mean=lambda xs:round(sum(xs)/len(xs),1) if xs else None
    results[model]={
      "gold_gloss_chrfpp":mean(gch),"gold_gloss_exact_agree":round(sum(gag)/len(gag),3) if gag else None,
      "gold_sentence_chrfpp":mean(sch),
      "broader_empty_rate":round(empty/len(broader),3),
      "broader_glosscount_mismatch_rate":round(mismatch/len(broader),3),
      "broader_noncyrillic_gloss_rate":round(noncyr/tot_bw,3),
      "broader_chrfpp_vs_incumbent":mean(inc_ch),
      "median_latency_s":round(sorted(lats)[len(lats)//2],2) if lats else None}
    print("   ",json.dumps(results[model],ensure_ascii=False))

# merge into any existing leaderboard so multi-key / incremental runs accumulate
prev=json.loads((O/"model_bakeoff.json").read_text()).get("models",{}) if (O/"model_bakeoff.json").exists() else {}
prev.update(results)
(O/"model_bakeoff.json").write_text(json.dumps({"broader_n":len(broader),"models":prev},ensure_ascii=False,indent=2))
print("\n=== LEADERBOARD (by gold gloss chrF++) ===")
print(f"{'model':34s} {'glossChrF':>9} {'exact':>6} {'sentChrF':>8} {'empty%':>6} {'lat_s':>6}")
for m,r in sorted(prev.items(), key=lambda kv:-(kv[1]['gold_gloss_chrfpp'] or 0)):
    print(f"{m:32s} {str(r['gold_gloss_chrfpp']):>9} {str(r['gold_gloss_exact_agree']):>6} "
          f"{str(r['gold_sentence_chrfpp']):>8} {100*r['broader_empty_rate']:>5.0f}% {str(r['median_latency_s']):>6}")
print("wrote out/model_bakeoff.json")
