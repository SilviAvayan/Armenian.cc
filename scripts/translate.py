#!/usr/bin/env python3
"""THE TRANSLATION COMPONENT ("your part" of the pipeline).

Input : ASR output — segments with `text` + ordered `words[]` (text/start/end/logprob),
        i.e. exactly what ElevenLabs produces, WITHOUT translations.
Output: the same segments enriched with per-word `translation` (in context),
        `explanation` (full-sentence translation) and `notes[]` — the eval-ready
        schema in SCHEMA.md. Glosses are merged back by index so ASR timings and
        logprob are preserved.

Usage:
  MOCK=1 python3 scripts/translate.py --in <asr.json> --out out/my_pipeline.json
  python3 scripts/translate.py --in <asr.json> --out out/my_pipeline.json \
        --model deepseek/deepseek-chat-v3.1 --target Russian
  # demo: derive a fake ASR input by stripping translations off the scraped corpus
  python3 scripts/translate.py --from-corpus --limit 20 --out out/my_pipeline.json
"""
import json, os, pathlib, argparse, threading, sys
from concurrent.futures import ThreadPoolExecutor, as_completed
import llm_tasks as T

HERE = pathlib.Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("--in", dest="inp")
ap.add_argument("--from-corpus", action="store_true",
                help="simulate ASR input by stripping translations off data/corpus.json")
ap.add_argument("--limit", type=int, default=0)
ap.add_argument("--out", default=str(HERE/"out"/"my_pipeline.json"))
ap.add_argument("--model", default="google/gemini-2.5-flash")  # matches team's ASR path; judge stays a different family
ap.add_argument("--target", default="Russian")
ap.add_argument("--workers", type=int, default=6)
args = ap.parse_args()

def strip_to_asr(seg):
    """Keep only what an ASR stage would emit."""
    return {"start":seg.get("start"),"end":seg.get("end"),"text":seg.get("text",""),
            "video_id":seg.get("video_id"),"seg_index":seg.get("seg_index"),
            "words":[{"text":w["text"],"start":w.get("start"),"end":w.get("end"),
                      "logprob":w.get("logprob")} for w in seg.get("words",[])]}

# ---- load ASR segments ----
if args.from_corpus:
    corpus = json.loads((HERE/"data"/"corpus.json").read_text())
    segs = [strip_to_asr(s) for s in corpus]
elif args.inp:
    raw = json.loads(pathlib.Path(args.inp).read_text())
    segs = raw if isinstance(raw, list) else next(iter(raw.values()))
    segs = [strip_to_asr(s) for s in segs]
else:
    raise SystemExit("provide --in <asr.json> or --from-corpus")
if args.limit: segs = segs[:args.limit]

CACHE = HERE/"out"/"translate_cache.json"
cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
lock = threading.Lock()
def ckey(s): return f"{args.model}::{args.target}::{s.get('video_id')}::{s.get('seg_index')}::{s['text'][:40]}"

warn = {"mismatch":0}
def do(seg):
    toks = [w["text"] for w in seg["words"]]
    if not toks: return seg
    k = ckey(seg)
    with lock: r = cache.get(k)
    if r is None:
        r = T.translate_segment(args.model, seg["text"], toks, target=args.target)
        with lock:
            cache[k]=r; CACHE.write_text(json.dumps(cache,ensure_ascii=False,indent=2))
    glosses = r.get("glosses") or []
    if len(glosses) != len(toks):
        warn["mismatch"] += 1
        glosses = (glosses + [""]*len(toks))[:len(toks)]   # pad/truncate to keep alignment
    for w, g in zip(seg["words"], glosses):
        w["translation"] = g
    seg["explanation"] = r.get("sentence","")
    seg["notes"] = r.get("notes",[]) or []
    return seg

out=[]; errs=0
with ThreadPoolExecutor(max_workers=args.workers) as ex:
    futs={ex.submit(do,s):i for i,s in enumerate(segs)}
    done=0
    for f in as_completed(futs):
        try: out.append((futs[f], f.result())); done+=1
        except Exception as e:
            errs+=1
            if errs<=3: print("  err:",e,file=sys.stderr)
        if done%20==0: print(f"  {done}/{len(segs)}")
out=[s for _,s in sorted(out,key=lambda x:x[0])]
pathlib.Path(args.out).write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(f"wrote {args.out}  ({len(out)} segments, {'MOCK' if T.MOCK else args.model})"
      f"  gloss-count mismatches: {warn['mismatch']}  errors: {errs}")
print(f"validate: python3 scripts/validate_pipeline_output.py {args.out}")
