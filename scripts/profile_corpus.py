#!/usr/bin/env python3
"""Profile the corpus to understand what we're evaluating and to design a
high-signal, stratified gold-label sample."""
import json, pathlib, statistics as st, re, math
from collections import Counter

HERE = pathlib.Path(__file__).resolve().parent.parent
corpus = json.loads((HERE / "data" / "corpus.json").read_text())
videos = json.loads((HERE / "data" / "videos.json").read_text())

n_seg = len(corpus)
words = [w for s in corpus for w in s.get("words", [])]
notes = [n for s in corpus for n in s.get("notes", [])]
logprobs = [w["logprob"] for w in words if isinstance(w.get("logprob"), (int, float))]

print(f"videos           {len(videos)}")
print(f"segments         {n_seg}")
print(f"words            {len(words)}")
print(f"notes            {len(notes)}")
print(f"words w/ logprob {len(logprobs)}  ({100*len(logprobs)/max(1,len(words)):.0f}%)")

# --- logprob distribution (ASR confidence) ---
logprobs.sort()
def pct(p):
    return logprobs[min(len(logprobs)-1, int(p*len(logprobs)))]
print("\nlogprob percentiles (0=certain, very negative=unsure):")
for p in (0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90):
    lp = pct(p)
    print(f"  p{int(p*100):>2}  {lp:8.3f}   (prob≈{math.exp(lp):.3f})")

# --- how many words are "low confidence" under a few thresholds ---
print("\nshare of words below logprob threshold (candidate 'flag'):")
for thr in (-0.3, -0.5, -0.7, -1.0, -1.5):
    n = sum(1 for lp in logprobs if lp < thr)
    print(f"  < {thr:>5}:  {n:5d}  ({100*n/len(logprobs):.1f}%)")

# --- genre proxy via handle ---
by_handle = Counter(c["handle"] for c in corpus)
print("\ntop handles (genre proxy):")
for h, c in by_handle.most_common(12):
    print(f"  {c:4d} seg  {h}")

# --- code-switching / non-Armenian tokens (latin/cyrillic inside Armenian text) ---
def has_latin(t): return bool(re.search(r"[A-Za-z]", t))
def has_cyr(t):   return bool(re.search(r"[А-Яа-яЁё]", t))
def is_num(t):    return bool(re.search(r"\d", t))
cs_latin = [w for w in words if has_latin(w["text"])]
cs_cyr   = [w for w in words if has_cyr(w["text"])]
nums     = [w for w in words if is_num(w["text"])]
print(f"\ncode-switch/loanword candidates:")
print(f"  latin-script tokens in AM text: {len(cs_latin)}")
print(f"  cyrillic-script tokens:         {len(cs_cyr)}")
print(f"  numeric tokens:                 {len(nums)}")

# --- polysemy candidates: same Armenian word form -> multiple distinct glosses ---
form2gloss = {}
for w in words:
    t = re.sub(r"[։,.\s]+$", "", w["text"]).strip()
    g = (w.get("translation") or "").strip().lower()
    if not t or not g:
        continue
    form2gloss.setdefault(t, Counter())[g] += 1
polysemous = {t: c for t, c in form2gloss.items()
              if len(c) >= 3 and sum(c.values()) >= 5}
poly_sorted = sorted(polysemous.items(), key=lambda kv: -sum(kv[1].values()))
print(f"\npolysemy candidates (>=3 distinct glosses, >=5 uses): {len(polysemous)}")
for t, c in poly_sorted[:12]:
    variants = ", ".join(f"{g}×{n}" for g, n in c.most_common(4))
    print(f"  {t:20s} -> {variants}")

# --- note types (what the model flags as tricky) ---
note_words = Counter(re.sub(r"\s+", " ", n.get("word","")).strip() for n in notes)
print(f"\nmost-noted words (model's own 'tricky' flags):")
for w, c in note_words.most_common(10):
    print(f"  {c:3d}  {w}")

# save derived artifacts for sampling
(HERE / "out").mkdir(exist_ok=True)
json.dump(
    {"polysemous": {t: dict(c) for t, c in poly_sorted}},
    open(HERE / "out" / "polysemy_candidates.json", "w"),
    ensure_ascii=False, indent=2)
print("\n✓ wrote out/polysemy_candidates.json")
