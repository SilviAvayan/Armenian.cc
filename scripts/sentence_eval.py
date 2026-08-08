#!/usr/bin/env python3
"""Sentence-level MT evaluation: human direct assessment (faithful/minor/major)
+ chrF++ of the model translation against the human reference."""
import json, pathlib, argparse
from collections import Counter
from chrf import chrf_pp

HERE=pathlib.Path(__file__).resolve().parent.parent
ap=argparse.ArgumentParser(); ap.add_argument("--refs", default=str(HERE/"out"/"sentence_refs.json")); a=ap.parse_args()
gold={p["id"]:p for p in json.loads((HERE/"out"/"gold_items.json").read_text())["phrases"]}
rp=pathlib.Path(a.refs)
if not rp.exists(): raise SystemExit(f"no refs at {rp} — rate in eval/sentences.html then Export")
S=json.loads(rp.read_text()).get("sentences",{})

rows=[]; ratings=Counter()
for pid,p in gold.items():
    r=S.get(pid)
    if not r or not r.get("rating"): continue
    ratings[r["rating"]]+=1
    hyp=p["explanation"]; ref=(r.get("reference") or "").strip() or hyp
    rows.append({"id":pid,"rating":r["rating"],"chrfpp":round(chrf_pp(hyp,ref),1),
                 "identical":hyp.strip()==ref.strip()})
if not rows: raise SystemExit("no rated sentences yet")

n=len(rows); mean=lambda xs: round(sum(xs)/len(xs),1) if xs else None
by_rating={rt:mean([x["chrfpp"] for x in rows if x["rating"]==rt]) for rt in ("faithful","minor","major")}
out={"n":n,"ratings":dict(ratings),
     "faithful_rate":round(ratings["faithful"]/n,3),
     "chrfpp_mean":mean([x["chrfpp"] for x in rows]),
     "chrfpp_by_rating":{k:v for k,v in by_rating.items() if v is not None},
     "n_identical_to_ref":sum(1 for x in rows if x["identical"]),
     "metric_note":"chrF++ (char 1-6 + word 1-2, beta=2). Single human reference; "
                   "sentences the human accepted unchanged score ~100 by construction. "
                   "BLEU intentionally not used (poor for Armenian morphology + tiny n).",
     "sentences":rows}
(HERE/"out"/"sentence_eval.json").write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(f"rated {n} sentences   faithful {100*out['faithful_rate']:.0f}%   "
      f"mean chrF++ {out['chrfpp_mean']}")
print("  by rating:", out["chrfpp_by_rating"])
print("wrote out/sentence_eval.json")
