#!/usr/bin/env python3
"""Corpus-wide probe for the 'copula/auxiliary gloss contamination' failure.

Armenian builds the present tense as [participle + auxiliary 'to be'] — e.g.
«սիրում եմ» = "I love", where «սիրում» carries the meaning and «եմ» is the
auxiliary "am". The incumbent glosser frequently mislocates the lexical meaning
onto the auxiliary («եմ→люблю», «է→идет», «է→на улице»), which teaches a learner
the wrong meaning for a function word.

This measures how often each copula/auxiliary form is glossed as something OTHER
than a plain 'be' sense. NOTE: this is an UPPER BOUND on the error rate, not the
error rate itself — some forms are homographs (ես = 'I' pronoun AND 'you are'),
so a non-'be' gloss is sometimes correct. Reported as 'non-copula gloss share'.
"""
import json, re, pathlib
from collections import Counter
HERE=pathlib.Path(__file__).resolve().parent.parent
corpus=json.loads((HERE/"data"/"corpus.json").read_text())
norm=lambda t:re.sub(r"[։՝՜՞,.\s]+","",t or "")
BE={"есть","это","быть","являюсь","являешься","является","являемся","являетесь",
    "","-","—","суть","вот","эти","этот"}
FORMS=["է","ա","են","ես","եմ","ենք","եք"]

out={}
for form in FORMS:
    gl=Counter()
    for s in corpus:
        for w in s.get("words",[]):
            if norm(w["text"])==form and w.get("translation") is not None:
                gl[w["translation"].strip().lower()]+=1
    tot=sum(gl.values())
    if not tot: continue
    nonbe=sum(c for g,c in gl.items() if g not in BE)
    out[form]={"n":tot,"non_copula_share":round(nonbe/tot,3),
               "top_glosses":gl.most_common(8)}

(HERE/"out"/"copula_probe.json").write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(f"{'form':6s} {'n':>4} {'non-copula share':>16}   top glosses")
for f,d in out.items():
    top=", ".join(f"{g or '∅'}×{c}" for g,c in d['top_glosses'][:5])
    print(f"{f:6s} {d['n']:>4} {d['non_copula_share']*100:>14.0f}%   {top}")
print("\nwrote out/copula_probe.json")
