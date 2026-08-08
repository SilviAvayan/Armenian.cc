#!/usr/bin/env python3
"""chrF / chrF++ (Popović 2015/2017) — character-n-gram F-score, no dependencies.

Chosen over BLEU because it is far more robust for morphologically rich languages
like Armenian (character overlap credits correct stems even under inflection) and
is stable on small test sets. chrF++ additionally mixes in word 1-/2-grams.

Score in [0,100]; beta=2 (recall weighted 2x), the standard setting.
"""
import re
from collections import Counter

def _char_ngrams(s, n):
    s = re.sub(r"\s+", "", s)          # chrF ignores whitespace for char n-grams
    return Counter(s[i:i+n] for i in range(len(s)-n+1)) if len(s) >= n else Counter()

def _word_ngrams(s, n):
    w = s.split()
    return Counter(tuple(w[i:i+n]) for i in range(len(w)-n+1)) if len(w) >= n else Counter()

def _fbeta(hyp, ref, beta=2.0):
    if not hyp or not ref: return None
    inter = sum((hyp & ref).values())
    if inter == 0: return 0.0
    p = inter/sum(hyp.values()); r = inter/sum(ref.values())
    b2 = beta*beta
    return (1+b2)*p*r/(b2*p+r) if (b2*p+r) else 0.0

def chrf(hyp, ref, char_order=6, word_order=0, beta=2.0):
    scores=[]
    for n in range(1, char_order+1):
        f=_fbeta(_char_ngrams(hyp,n), _char_ngrams(ref,n), beta)
        if f is not None: scores.append(f)
    for n in range(1, word_order+1):
        f=_fbeta(_word_ngrams(hyp,n), _word_ngrams(ref,n), beta)
        if f is not None: scores.append(f)
    return 100.0*sum(scores)/len(scores) if scores else 0.0

def chrf_pp(hyp, ref, beta=2.0):
    """chrF++ : char n-grams 1..6 + word n-grams 1..2."""
    return chrf(hyp, ref, char_order=6, word_order=2, beta=beta)

if __name__ == "__main__":
    # sanity: identical -> 100; unrelated -> low; paraphrase -> mid
    a="Тесто я раскатываю, потом округло скатываю."
    print("identical:", round(chrf_pp(a,a),1))
    print("close    :", round(chrf_pp("Тесто раскатываю, потом скатываю округло.", a),1))
    print("unrelated:", round(chrf_pp("Совершенно другое предложение здесь.", a),1))
