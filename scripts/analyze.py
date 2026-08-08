#!/usr/bin/env python3
"""Offline analysis — needs only the stratified sample + human gold labels.
No LLM calls. Produces out/results.json and out/report.md.

Computes:
  1. Overall + per-stratum gloss accuracy, with Wilson 95% CIs (honest on small n).
  2. Mis-transcription (ASR) rate, and its overlap with low confidence.
  3. UNCERTAINTY: does ASR logprob predict gloss error?  ROC-AUC + a picked
     operating threshold with precision/recall (the 'flag low-confidence words'
     feature, measured — not asserted).
  4. Phrase-translation adequacy distribution.
"""
import json, pathlib, math, argparse
from collections import defaultdict, Counter

HERE = pathlib.Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("--labels", default=str(HERE/"out"/"gold_labels.json"))
args = ap.parse_args()

gold = json.loads((HERE/"out"/"gold_items.json").read_text())
lab_path = pathlib.Path(args.labels)
if not lab_path.exists():
    raise SystemExit(f"no labels at {lab_path} — export from eval/label.html first "
                     f"(or run make_mock_labels.py + pass --labels out/gold_labels.mock.json)")
L = json.loads(lab_path.read_text())
labels = L.get("labels", L)
IS_MOCK = bool(L.get("_mock"))

items = {it["id"]: it for it in gold["words"]}
phrases = {it["id"]: it for it in gold["phrases"]}

# ---- helpers ----
def wilson(k, n, z=1.96):
    if n == 0: return (0.0, 0.0, 0.0)
    p = k/n
    d = 1 + z*z/n
    c = (p + z*z/(2*n))/d
    h = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/d
    return (p, max(0,c-h), min(1,c+h))

def auc(scores_labels):
    """AUC that higher score -> more likely positive. Handles ties (rank avg)."""
    pos = [s for s,y in scores_labels if y==1]
    neg = [s for s,y in scores_labels if y==0]
    if not pos or not neg: return float("nan")
    data = sorted(scores_labels, key=lambda x:x[0])
    ranks = {}; i=0; n=len(data)
    while i<n:
        j=i
        while j<n and data[j][0]==data[i][0]: j+=1
        r=(i+1+j)/2.0
        for k in range(i,j): ranks[k]=r
        i=j
    sum_pos_ranks=sum(ranks[idx] for idx,(s,y) in enumerate(data) if y==1)
    np_,nn=len(pos),len(neg)
    return (sum_pos_ranks - np_*(np_+1)/2)/(np_*nn)

# ---- join ----
rows=[]
for wid, it in items.items():
    r = labels.get(wid)
    if not r or not r.get("verdict"): continue
    v=r["verdict"]
    if v=="unsure": continue
    rows.append({
        "id":wid,"stratum":it.get("stratum","?"),"logprob":it.get("logprob"),
        "asr_difficulty":it.get("asr_difficulty"),
        "verdict":v,
        # strict: ONLY 'correct' passes (acceptable counts as an error) -> lower acc
        "error_strict": v in ("wrong","acceptable"),
        # lenient: 'acceptable' also passes; only clear 'wrong' is an error -> higher acc
        "error_lenient": v=="wrong",
        # the clear-error signal used for uncertainty/ASR analysis
        "is_wrong": v=="wrong",
        "mistranscribed": bool(r.get("mistranscribed")),
        "word":it.get("word"),"gloss":it.get("gloss"),
        "correction":r.get("correction",""),
    })
N=len(rows)

# ---- 1. accuracy overall + per stratum ----
def acc_block(subset, err_key):
    n=len(subset); k=sum(1 for r in subset if not r[err_key])
    p,lo,hi=wilson(k,n)
    return {"n":n,"correct":k,"acc":round(p,3),"ci95":[round(lo,3),round(hi,3)]}

overall={"strict":acc_block(rows,"error_strict"),
         "lenient":acc_block(rows,"error_lenient")}
by_stratum={}
for s in sorted(set(r["stratum"] for r in rows)):
    sub=[r for r in rows if r["stratum"]==s]
    by_stratum[s]={"strict":acc_block(sub,"error_strict"),
                   "lenient":acc_block(sub,"error_lenient")}

# gloss accuracy by ASR-difficulty category (team's labeled videos only)
by_difficulty={}
for c in ["formal","single_speaker","multi_speakers","songs","difficult","songs_difficult"]:
    sub=[r for r in rows if r["asr_difficulty"]==c]
    if sub: by_difficulty[c]=acc_block(sub,"error_strict")

# ---- 2. mis-transcription ----
mis=[r for r in rows if r["mistranscribed"]]
mis_rate=wilson(len(mis),N)
# of gloss errors, how many are ASR-caused?
strict_err=[r for r in rows if r["is_wrong"]]
asr_caused=sum(1 for r in strict_err if r["mistranscribed"])
mis_block={"mis_rate":round(mis_rate[0],3),"mis_ci":[round(mis_rate[1],3),round(mis_rate[2],3)],
           "n_mis":len(mis),
           "share_of_errors_ASR_caused": round(asr_caused/len(strict_err),3) if strict_err else None,
           "n_strict_errors":len(strict_err)}

# ---- 3. uncertainty: logprob predicts error? ----
scored=[(-(r["logprob"] or 0.0), 1 if r["is_wrong"] else 0)
        for r in rows if r["logprob"] is not None]
au=auc(scored)
# also for mistranscription (ASR's own signal predicting ASR's own errors)
scored_mis=[(-(r["logprob"] or 0.0), 1 if r["mistranscribed"] else 0)
            for r in rows if r["logprob"] is not None]
au_mis=auc(scored_mis)
# operating thresholds on raw logprob (flag words BELOW threshold)
thr_rows=[r for r in rows if r["logprob"] is not None]
flag_table=[]
for thr in (-0.2,-0.3,-0.4,-0.5,-0.7,-1.0):
    flagged=[r for r in thr_rows if r["logprob"]<thr]
    tp=sum(1 for r in flagged if r["is_wrong"])
    fp=len(flagged)-tp
    fn=sum(1 for r in thr_rows if r["is_wrong"] and not (r["logprob"]<thr))
    prec=tp/len(flagged) if flagged else float("nan")
    rec=tp/(tp+fn) if (tp+fn) else float("nan")
    flag_table.append({"threshold":thr,"n_flagged":len(flagged),
        "precision":round(prec,3) if prec==prec else None,
        "recall":round(rec,3) if rec==rec else None,
        "coverage":round(len(flagged)/len(thr_rows),3)})

# ---- 4. phrases ----
pv=Counter(labels[pid]["verdict"] for pid in phrases if labels.get(pid,{}).get("verdict"))
phrase_block={"n":sum(pv.values()),"dist":dict(pv),
    "faithful_rate":round(pv.get("faithful",0)/max(1,sum(pv.values())),3)}

results={"is_mock":IS_MOCK,"n_word_items_labeled":N,
    "overall":overall,"by_stratum":by_stratum,"by_asr_difficulty":by_difficulty,
    "mistranscription":mis_block,
    "uncertainty":{"auc_logprob_vs_glosserror":round(au,3) if au==au else None,
                   "auc_logprob_vs_mistranscription":round(au_mis,3) if au_mis==au_mis else None,
                   "flag_operating_points":flag_table},
    "phrase_translation":phrase_block}
(HERE/"out"/"results.json").write_text(json.dumps(results,ensure_ascii=False,indent=2))

# ---- report.md ----
def pct(x): return f"{100*x:.0f}%"
lines=[]
if IS_MOCK: lines.append("> ⚠️ **MOCK DATA** — numbers below are synthetic, for pipeline validation only.\n")
lines.append(f"# armenian.cc — LLM evaluation results\n")
lines.append(f"Human-labeled word items: **{N}**  ·  phrase items: **{phrase_block['n']}**\n")
lines.append("## 1. Gloss accuracy (per-word, in context)\n")
o=overall["strict"]; ol=overall["lenient"]
lines.append(f"- **Strict** (only 'correct' counts): **{pct(o['acc'])}** "
             f"(95% CI {pct(o['ci95'][0])}–{pct(o['ci95'][1])}, n={o['n']})")
lines.append(f"- **Lenient** ('acceptable' allowed): **{pct(ol['acc'])}** "
             f"(95% CI {pct(ol['ci95'][0])}–{pct(ol['ci95'][1])})\n")
lines.append("| stratum | n | strict acc | 95% CI |")
lines.append("|---|--:|--:|--|")
name={"A_colloquial":"A colloquial/slang","B_polysemy":"B polysemy (WSD)",
      "C_lowconf":"C low ASR-confidence","D_codeswitch":"D code-switch/loanword",
      "E_control":"E control (easy)"}
for s,b in sorted(by_stratum.items()):
    st=b["strict"]
    lines.append(f"| {name.get(s,s)} | {st['n']} | {pct(st['acc'])} | "
                 f"{pct(st['ci95'][0])}–{pct(st['ci95'][1])} |")
lines.append("")
lines.append("## 2. Transcription (ASR) errors\n")
mb=mis_block
lines.append(f"- Mis-transcription rate: **{pct(mb['mis_rate'])}** "
             f"(95% CI {pct(mb['mis_ci'][0])}–{pct(mb['mis_ci'][1])})")
if mb["share_of_errors_ASR_caused"] is not None:
    lines.append(f"- **{pct(mb['share_of_errors_ASR_caused'])}** of gloss errors are actually "
                 f"caused upstream by ASR mis-hearing the word (not the translator's fault).\n")
lines.append("## 3. Uncertainty — does the shipped ASR confidence predict errors?\n")
u=results["uncertainty"]
lines.append(f"- AUC(logprob → gloss error): **{u['auc_logprob_vs_glosserror']}**  "
             f"(0.5=useless, 1.0=perfect)")
lines.append(f"- AUC(logprob → mis-transcription): **{u['auc_logprob_vs_mistranscription']}**\n")
lines.append("| flag threshold (logprob<) | words flagged | coverage | precision | recall |")
lines.append("|--:|--:|--:|--:|--:|")
for f in u["flag_operating_points"]:
    lines.append(f"| {f['threshold']} | {f['n_flagged']} | {pct(f['coverage'])} | "
                 f"{f['precision']} | {f['recall']} |")
lines.append("")
lines.append("## 4. Phrase-level translation adequacy\n")
lines.append(f"- Faithful: **{pct(phrase_block['faithful_rate'])}**  ·  dist: {phrase_block['dist']}\n")
(HERE/"out"/"report.md").write_text("\n".join(lines))

print(f"{'[MOCK] ' if IS_MOCK else ''}analyzed {N} word items.")
print(f"  overall strict acc = {pct(overall['strict']['acc'])}  "
      f"AUC(logprob->error) = {u['auc_logprob_vs_glosserror']}  "
      f"AUC(logprob->mistrans) = {u['auc_logprob_vs_mistranscription']}")
print("  wrote out/results.json, out/report.md")
