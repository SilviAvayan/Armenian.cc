#!/usr/bin/env python3
"""Generate a PLAUSIBLE mock gold_labels.json so we can validate analyze.py
end-to-end before the real human labels arrive. Errors are injected with a
realistic structure: more likely at low logprob, in colloquial/code-switch
strata, so the ROC/AUC machinery has signal to find. THIS IS NOT REAL DATA —
analyze.py prints a loud MOCK banner when it detects it."""
import json, pathlib, random, math
HERE = pathlib.Path(__file__).resolve().parent.parent
gold = json.loads((HERE/"out"/"gold_items.json").read_text())
rng = random.Random(7)

def p_error(it):
    lp = it.get("logprob") or 0.0
    p = 0.06                                   # base error rate
    p += min(0.5, max(0.0, -lp) * 0.35)        # low confidence -> more errors
    p += {"A_colloquial":0.18,"D_codeswitch":0.22,"B_polysemy":0.10,
          "C_lowconf":0.15,"E_control":0.0}.get(it.get("stratum"),0.0)
    return min(0.85, p)

labels = {}
for it in gold["words"]:
    pe = p_error(it)
    r = rng.random()
    if r < pe*0.6:      v="wrong"
    elif r < pe:        v="acceptable"
    else:               v="correct"
    mis = (it.get("logprob") or 0) < -0.6 and rng.random() < 0.5
    labels[it["id"]] = {"verdict":v,"mistranscribed":bool(mis),
                        "correction":"<mock>" if v!="correct" else ""}
for it in gold["phrases"]:
    r=rng.random(); v="faithful" if r<0.7 else ("minor" if r<0.9 else "major")
    labels[it["id"]] = {"verdict":v,"correction":""}

out={"labeled_at":"MOCK","_mock":True,"labels":labels}
(HERE/"out"/"gold_labels.mock.json").write_text(json.dumps(out,ensure_ascii=False,indent=2))
print("wrote out/gold_labels.mock.json (MOCK)")
