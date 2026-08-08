#!/usr/bin/env python3
"""Turn human-flagged errors into a FAILURE TAXONOMY with counts + real examples.
Each error is assigned to the first matching bucket (most-specific first):
  ASR-propagated   -> the Armenian word was mis-heard (learner sees a real word,
                      wrong one); translation then can't win.
  code-switch/NER  -> latin/cyrillic/numeric token (loanword, brand, name).
  wrong-sense      -> polysemy stratum: right word, wrong contextual sense.
  colloquial/slang -> spoken/dialectal form a dictionary wouldn't cover.
  translation      -> everything else (plain mistranslation / fluency).
"""
import json, pathlib, re, argparse
from collections import defaultdict

HERE=pathlib.Path(__file__).resolve().parent.parent
ap=argparse.ArgumentParser()
ap.add_argument("--labels", default=str(HERE/"out"/"gold_labels.json"))
args=ap.parse_args()
gold=json.loads((HERE/"out"/"gold_items.json").read_text())
L=json.loads(pathlib.Path(args.labels).read_text()); labels=L.get("labels",L)
items={it["id"]:it for it in gold["words"]}

def bucket(it,h):
    w=it["word"]
    if h.get("mistranscribed"): return "ASR-propagated"
    if re.search(r"[A-Za-z]|[А-Яа-яЁё]|\d",w): return "code-switch/NER"
    if it["stratum"]=="B_polysemy": return "wrong-sense (polysemy)"
    if it["stratum"]=="A_colloquial" or it.get("note"): return "colloquial/slang"
    return "translation/other"

buckets=defaultdict(list)
n_err=0
for wid,it in items.items():
    h=labels.get(wid)
    if not h or h.get("verdict") in (None,"unsure"): continue
    is_err = h["verdict"] in ("wrong","acceptable") or h.get("mistranscribed")
    if not is_err: continue
    n_err+=1
    buckets[bucket(it,h)].append({
        "word":it["word"],"gloss":it["gloss"],
        "correction":h.get("correction",""),"verdict":h["verdict"],
        "seg":it["seg_text"][:80],"handle":it.get("handle")})

summary={k:len(v) for k,v in sorted(buckets.items(),key=lambda kv:-len(kv[1]))}
out={"n_errors":n_err,"by_category":summary,
     "examples":{k:v[:4] for k,v in buckets.items()}}
(HERE/"out"/"failures.json").write_text(json.dumps(out,ensure_ascii=False,indent=2))

# markdown
lines=["## Failure taxonomy\n",f"Total flagged errors: **{n_err}**\n",
       "| category | count | share |","|---|--:|--:|"]
for k,c in summary.items():
    lines.append(f"| {k} | {c} | {round(100*c/max(1,n_err))}% |")
lines.append("\n### Representative failures\n")
for k,v in buckets.items():
    lines.append(f"**{k}**")
    for e in v[:3]:
        corr=f" → should be «{e['correction']}»" if e['correction'] else ""
        lines.append(f"- «{e['word']}» glossed «{e['gloss']}»{corr}  "
                     f"<br><sub>{e['seg']}… (@{e['handle']})</sub>")
    lines.append("")
(HERE/"out"/"failures.md").write_text("\n".join(lines))
print(f"errors={n_err}  categories={summary}")
print("wrote out/failures.json, out/failures.md")
