#!/usr/bin/env python3
"""WER/CER of whole-video transcripts (dataset/transcripts/<model>/<category>/<id>.txt)
vs the human-corrected segment references, for every model side by side.

Unlike asr_wer.py (which grades the corpus segment texts), the hypothesis here is an
unsegmented full-video transcript, so each reference is scored against the
best-matching contiguous window of the transcript (infix alignment: prefix/suffix
words of the hypothesis outside the window are skipped for free). The 25 sampled
segments (video, timestamps, ElevenLabs text) are read from eval/asr.html where
build_asr_tool.py embedded them, so out/asr_items.json is not required."""
import json, pathlib, re, os, argparse
from collections import defaultdict

HERE=pathlib.Path(__file__).resolve().parent.parent
ap=argparse.ArgumentParser()
ap.add_argument("--refs", default=str(HERE/"out"/"asr_refs.json"))
ap.add_argument("--dataset", default=os.environ.get("VIDEOS_DATASET_LABELED",
                str(HERE.parent/"videos_dataset_labeled")),
                help="folder tree whose subdir names give each video's category")
ap.add_argument("--transcripts", default=str(HERE/"dataset"/"transcripts"),
                help="evaluate every <model>/<category>/<video_id>.txt under this dir")
a=ap.parse_args()

rp=pathlib.Path(a.refs)
if not rp.exists(): raise SystemExit(f"no refs at {rp} — check transcripts in eval/asr.html then Export")
refs=json.loads(rp.read_text()).get("refs",{})
html=(HERE/"eval"/"asr.html").read_text()
items=json.loads(re.search(r"const DATA=(\[.*?\]);const KEY",html,re.S).group(1))
cat_of={p.stem:p.parent.name for p in pathlib.Path(a.dataset).glob("*/*.mp4")}

# keep in sync with asr_wer.py
def norm(t): return re.sub(r"[։՝՜՞՛'’,.\-—«»…:;!?]"," ",(t or "").lower()).replace("եւ","և")
def toks(t): return norm(t).split()
def infix_dist(ref,hyp):  # min edits turning some contiguous window of hyp into ref
    n,m=len(ref),len(hyp); prev=[0]*(m+1)
    for i in range(1,n+1):
        cur=[i]+[0]*m
        for j in range(1,m+1):
            cur[j]=min(prev[j]+1,cur[j-1]+1,prev[j-1]+(ref[i-1]!=hyp[j-1]))
        prev=cur
    return min(prev)

models=sorted(d for d in pathlib.Path(a.transcripts).iterdir() if d.is_dir())
CATS=["formal","single_speaker","multi_speakers","songs","difficult","songs_difficult"]
out={"n_refs":sum(1 for r in refs.values() if r.get("done")),"models":{}}
print(f"{'model':34s} {'n':>3} "+" ".join(f"{c[:12]:>13}" for c in CATS if c in set(cat_of.values()))+f" {'ALL WER':>8} {'ALL CER':>8}")
for tdir in models:
    agg=defaultdict(lambda:[0,0,0,0])  # cat -> [word_edits, word_ref, char_edits, char_ref]
    clips=[]
    for it in items:
        r=refs.get(it["id"])
        if not r or not r.get("done"): continue
        vid=re.match(r"video_(.+)\.mp4$",it["src"].rsplit("/",1)[1]).group(1)
        cat=cat_of.get(vid)
        if cat is None: continue
        f=tdir/cat/f"{vid}.txt"
        if not f.exists(): continue
        ref,hyp=r["reference"],f.read_text()
        ra,ha=toks(ref),toks(hyp); we=infix_dist(ra,ha); wn=max(1,len(ra))
        rc,hc=list(re.sub(r"\s","",norm(ref))),list(re.sub(r"\s","",norm(hyp)))
        ce=infix_dist(rc,hc); cn=max(1,len(rc))
        for k,v in ((0,we),(1,wn),(2,ce),(3,cn)): agg[cat][k]+=v; agg["ALL"][k]+=v
        clips.append({"id":it["id"],"video":vid,"category":cat,
                      "wer":round(we/wn,3),"cer":round(ce/cn,3)})
    if not clips: continue
    row=" ".join((f"{agg[c][0]/max(1,agg[c][1]):>13.3f}" if c in agg else f"{'-':>13}")
                 for c in CATS if c in set(cat_of.values()))
    print(f"{tdir.name:34s} {len(clips):>3} {row} "
          f"{agg['ALL'][0]/max(1,agg['ALL'][1]):>8.3f} {agg['ALL'][2]/max(1,agg['ALL'][3]):>8.3f}")
    out["models"][tdir.name]={"overall":{"WER":round(agg["ALL"][0]/max(1,agg["ALL"][1]),3),
        "CER":round(agg["ALL"][2]/max(1,agg["ALL"][3]),3),"ref_words":agg["ALL"][1]},
        "by_category":{c:{"WER":round(agg[c][0]/max(1,agg[c][1]),3),
                          "CER":round(agg[c][2]/max(1,agg[c][3]),3)} for c in CATS if c in agg},
        "clips":clips}
(HERE/"out"/"asr_wer_models.json").write_text(json.dumps(out,ensure_ascii=False,indent=2))
print("wrote out/asr_wer_models.json")
