#!/usr/bin/env python3
"""Render headline results as standalone SVGs (no deps -> fully reproducible):
   chart_stratum.svg   per-stratum gloss accuracy + 95% CI
   chart_flag.svg      precision/recall of the low-confidence flag vs coverage
   chart_baseline.svg  context vs no-context vs production accuracy (if present)
"""
import json, pathlib
HERE=pathlib.Path(__file__).resolve().parent.parent
OUT=HERE/"out"
res=json.loads((OUT/"results.json").read_text())

def bars(path,title,cats,vals,cis=None,colors=None,ymax=1.0,note=""):
    W,H=680,340; padL,padB,padT=60,70,50; bw=(W-padL-30)/len(cats)
    def y(v):return padT+(1-v/ymax)*(H-padT-padB)
    s=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="-apple-system,Segoe UI,sans-serif">']
    s.append(f'<rect width="{W}" height="{H}" fill="#0f1115"/>')
    s.append(f'<text x="{padL}" y="26" fill="#e8eaed" font-size="16" font-weight="600">{title}</text>')
    for g in (0,.25,.5,.75,1.0):
        yy=y(g); s.append(f'<line x1="{padL}" y1="{yy:.0f}" x2="{W-20}" y2="{yy:.0f}" stroke="#2b2f38"/>')
        s.append(f'<text x="{padL-8}" y="{yy+4:.0f}" fill="#9aa0aa" font-size="11" text-anchor="end">{int(g*100)}%</text>')
    for i,(c,v) in enumerate(zip(cats,vals)):
        if v is None: continue
        x=padL+i*bw+8; col=(colors[i] if colors else "#58a6ff")
        s.append(f'<rect x="{x:.0f}" y="{y(v):.0f}" width="{bw-16:.0f}" height="{H-padB-y(v):.0f}" fill="{col}" rx="4"/>')
        s.append(f'<text x="{x+(bw-16)/2:.0f}" y="{y(v)-6:.0f}" fill="#e8eaed" font-size="12" text-anchor="middle">{int(round(v*100))}%</text>')
        if cis and cis[i]:
            lo,hi=cis[i]; cx=x+(bw-16)/2
            s.append(f'<line x1="{cx:.0f}" y1="{y(lo):.0f}" x2="{cx:.0f}" y2="{y(hi):.0f}" stroke="#e8eaed" stroke-width="1.5"/>')
            s.append(f'<line x1="{cx-5:.0f}" y1="{y(lo):.0f}" x2="{cx+5:.0f}" y2="{y(lo):.0f}" stroke="#e8eaed"/>')
            s.append(f'<line x1="{cx-5:.0f}" y1="{y(hi):.0f}" x2="{cx+5:.0f}" y2="{y(hi):.0f}" stroke="#e8eaed"/>')
        for j,ln in enumerate(c.split("\n")):
            s.append(f'<text x="{x+(bw-16)/2:.0f}" y="{H-padB+16+j*13:.0f}" fill="#9aa0aa" font-size="10.5" text-anchor="middle">{ln}</text>')
    if note: s.append(f'<text x="{padL}" y="{H-8}" fill="#9aa0aa" font-size="10">{note}</text>')
    s.append('</svg>')
    (OUT/path).write_text("\n".join(s)); print("wrote",path)

# 1. per-stratum accuracy
NAMES={"E_control":"control\n(easy)","B_polysemy":"polysemy\n(WSD)","C_lowconf":"low ASR\nconf",
       "A_colloquial":"colloquial\n/slang","D_codeswitch":"code-switch\n/loanword"}
order=["E_control","B_polysemy","C_lowconf","A_colloquial","D_codeswitch"]
bs=res["by_stratum"]
cats=[NAMES[s] for s in order if s in bs]
vals=[bs[s]["strict"]["acc"] for s in order if s in bs]
cis=[bs[s]["strict"]["ci95"] for s in order if s in bs]
cols=["#3fb950","#58a6ff","#58a6ff","#d29922","#f85149"][:len(cats)]
bars("chart_stratum.svg","Gloss accuracy by difficulty stratum (strict, 95% CI)",
     cats,vals,cis,cols,note=f"n per bar varies · overall strict {int(res['overall']['strict']['acc']*100)}%")

# 2. flag precision/recall
fp=res["uncertainty"]["flag_operating_points"]
cats2=[f"<{f['threshold']}\n{int(f['coverage']*100)}% cov" for f in fp]
prec=[f["precision"] or 0 for f in fp]
bars("chart_flag.svg","Low-confidence flag: precision at each logprob threshold",
     cats2,prec,None,["#8957e5"]*len(cats2),
     note=f"AUC(logprob→error)={res['uncertainty']['auc_logprob_vs_glosserror']}  ·  AUC(→mis-transcription)={res['uncertainty']['auc_logprob_vs_mistranscription']}")

# 3. baseline (optional)
bl=OUT/"baseline.json"
if bl.exists():
    b=json.loads(bl.read_text())["per_stratum"]
    order2=[s for s in ["A_colloquial","B_polysemy","D_codeswitch","ALL"] if s in b]
    # grouped: draw three separate mini not trivial; instead show noctx vs ctx for key strata
    cats3=[]; vals3=[]; cols3=[]
    for s in order2:
        cats3+= [f"{s.split('_')[0]}\nno-ctx", f"{s.split('_')[0]}\nctx"]
        vals3+= [b[s]["noctx"], b[s]["ctx"]]
        cols3+= ["#f85149","#3fb950"]
    bars("chart_baseline.svg","LLM earns its place: no-context vs in-context gloss accuracy",
         cats3,vals3,None,cols3,note="red=dictionary-style (no context) · green=with context")
# 4. ASR confidence by difficulty category
ad=OUT/"asr_difficulty.json"
if ad.exists():
    c=json.loads(ad.read_text())["confidence_by_category"]
    order=[k for k in ["formal","single_speaker","multi_speakers","songs","difficult","songs_difficult"] if k in c]
    cats4=[k.replace("_","\n") for k in order]
    vals4=[c[k]["low_conf_rate"] for k in order]
    cols4=["#3fb950","#3fb950","#d29922","#d29922","#f85149","#f85149"][:len(order)]
    bars("chart_asr_difficulty.svg","ElevenLabs low-confidence word rate by human difficulty rating",
         cats4,vals4,None,cols4,ymax=max(0.12,max(vals4)*1.25),
         note="higher = ASR less sure · confidence degrades monotonically with rated difficulty")

# 5. WER by difficulty (human ground truth)
wj=OUT/"asr_wer.json"
if wj.exists():
    w=json.loads(wj.read_text())["by_category"]
    order=[k for k in ["formal","single_speaker","multi_speakers","songs","difficult","songs_difficult"] if k in w]
    cats5=[k.replace("_","\n") for k in order]
    vals5=[w[k]["WER"] for k in order]
    cols5=["#3fb950","#3fb950","#d29922","#d29922","#f85149","#f85149"][:len(order)]
    bars("chart_wer.svg","ElevenLabs word error rate by difficulty (human-checked, n=5/cat)",
         cats5,vals5,None,cols5,ymax=max(0.25,max(vals5)*1.2),
         note="WER vs human-corrected transcript · same ranking as the confidence signal")

print("charts done")
