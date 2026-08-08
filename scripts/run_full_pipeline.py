#!/usr/bin/env python3
"""Full end-to-end run: for every ElevenLabs Scribe transcript, bridge to segments
and run the translation stage → eval-ready per-video JSON under out/pipeline_full/.
This is the genuine ASR→translate pipeline on the real ASR output (all 6 categories)."""
import json, pathlib, glob, threading, argparse, hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
import llm_tasks as T
from asr_to_segments import load_words, segment

HERE=pathlib.Path(__file__).resolve().parent.parent; O=HERE/"out"
ap=argparse.ArgumentParser()
ap.add_argument("--model", default="google/gemini-2.5-flash")
ap.add_argument("--asr-dir", default=str(HERE/"dataset"/"transcripts"/"elevenlabs_scribe_v2.basic"))
ap.add_argument("--workers", type=int, default=8)
a=ap.parse_args()
OUTDIR=O/"pipeline_full"; OUTDIR.mkdir(parents=True, exist_ok=True)

CACHE=O/"full_pipeline_cache.json"; cache=json.loads(CACHE.read_text()) if CACHE.exists() else {}
lock=threading.Lock()
def ckey(text): return f"{a.model}::"+hashlib.md5(text.encode()).hexdigest()
def translate_seg(seg):
    toks=[w["text"] for w in seg.get("words",[])]
    if not toks: return {"sentence":"","glosses":[],"notes":[]}
    k=ckey(seg["text"])
    with lock:
        if k in cache: return cache[k]
    r=T.translate_segment(a.model, seg["text"], toks, target="Russian")
    with lock: cache[k]=r; CACHE.write_text(json.dumps(cache,ensure_ascii=False,indent=2))
    return r

files=sorted(glob.glob(str(pathlib.Path(a.asr_dir)/"*"/"*.json")))
print(f"videos: {len(files)}  model: {a.model}")

def do_video(path):
    p=pathlib.Path(path); cat=p.parent.name; vid=p.stem
    words=load_words(path)
    segs=segment(words)
    n=0
    for s in segs:
        r=translate_seg(s)
        gl=r.get("glosses") or []
        if len(gl)!=len(s["words"]): gl=(gl+[""]*len(s["words"]))[:len(s["words"])]
        for w,g in zip(s["words"], gl): w["translation"]=g
        s["explanation"]=r.get("sentence",""); s["notes"]=r.get("notes",[]) or []
        n+=1
    (OUTDIR/f"{cat}__{vid}.json").write_text(json.dumps(segs,ensure_ascii=False,indent=2))
    return vid, len(segs), sum(len(s["words"]) for s in segs)

done=vids=segs_tot=words_tot=0
with ThreadPoolExecutor(max_workers=a.workers) as ex:
    futs={ex.submit(do_video,f):f for f in files}
    for fu in as_completed(futs):
        try:
            vid,ns,nw=fu.result(); vids+=1; segs_tot+=ns; words_tot+=nw
        except Exception as e:
            print("  ERR",futs[fu],e)
        done+=1
        if done%15==0: print(f"  {done}/{len(files)} videos")
print(f"\n✓ full pipeline: {vids} videos, {segs_tot} segments, {words_tot} words")
print(f"  output: out/pipeline_full/*.json  (eval-ready per SCHEMA.md)")
