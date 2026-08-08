#!/usr/bin/env python3
"""WER/CER of ElevenLabs transcript vs the human-corrected reference, overall
and BY DIFFICULTY CATEGORY. No ASR is built — this grades ElevenLabs' output."""
import json, pathlib, re, argparse
from collections import defaultdict
HERE=pathlib.Path(__file__).resolve().parent.parent
ap=argparse.ArgumentParser(); ap.add_argument("--refs", default=str(HERE/"out"/"asr_refs.json")); a=ap.parse_args()
items={s["id"]:s for s in json.loads((HERE/"out"/"asr_items.json").read_text())}
rp=pathlib.Path(a.refs)
if not rp.exists(): raise SystemExit(f"no refs at {rp} — check transcripts in eval/asr.html then Export")
refs=json.loads(rp.read_text()).get("refs",{})

def toks(t): return re.sub(r"[։՝՜՞,.\-—«»…]"," ",t or "").split()
def dist(a,b):  # Levenshtein
    n,m=len(a),len(b); d=list(range(m+1))
    for i in range(1,n+1):
        prev=d[0]; d[0]=i
        for j in range(1,m+1):
            cur=d[j]; d[j]=min(d[j]+1,d[j-1]+1,prev+(a[i-1]!=b[j-1])); prev=cur
    return d[m]

agg=defaultdict(lambda:[0,0,0,0])  # cat -> [word_edits, word_ref, char_edits, char_ref]
rows=[]; done=0
for id_,it in items.items():
    r=refs.get(id_)
    if not r or not r.get("done"): continue
    done+=1
    hyp,ref=it["text"], r.get("reference",it["text"])
    ha,ra=toks(hyp),toks(ref); we=dist(ha,ra); wn=max(1,len(ra))
    hc,rc=list(re.sub(r"\s","",hyp)),list(re.sub(r"\s","",ref)); ce=dist(hc,rc); cn=max(1,len(rc))
    c=it["category"]
    for key,val in ((0,we),(1,wn),(2,ce),(3,cn)):
        agg[c][key]+=val; agg["ALL"][key]+=val
    rows.append({"id":id_,"category":c,"wer":round(we/wn,3),"cer":round(ce/cn,3),
                 "unchanged":bool(r.get("unchanged"))})

if not done: raise SystemExit("no completed refs yet")
def block(v): return {"WER":round(v[0]/max(1,v[1]),3),"CER":round(v[2]/max(1,v[3]),3),"ref_words":v[1]}
out={"n_clips":done,"overall":block(agg["ALL"]),
     "by_category":{c:block(agg[c]) for c in
        ["formal","single_speaker","multi_speakers","songs","difficult","songs_difficult"] if c in agg},
     "clean_rate":round(sum(1 for r in rows if r["unchanged"])/len(rows),3),
     "clips":rows}
(HERE/"out"/"asr_wer.json").write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(f"clips checked: {done}   overall WER {out['overall']['WER']}  CER {out['overall']['CER']}  "
      f"({out['clean_rate']*100:.0f}% needed no fix)")
print(f"{'category':16s} {'clips':>5} {'WER':>6} {'CER':>6}")
for c,b in out["by_category"].items():
    n=sum(1 for r in rows if r['category']==c)
    print(f"{c:16s} {n:>5} {b['WER']:>6} {b['CER']:>6}")
print("wrote out/asr_wer.json")
