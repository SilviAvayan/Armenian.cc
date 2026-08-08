#!/usr/bin/env python3
"""Build a STRATIFIED gold-label sample. Random sampling would waste the
labeler's time on easy words; we deliberately over-sample the cases that
stress each rubric dimension, and keep an 'easy random' control stratum so we
can measure false-alarm rates and prove the model is fine where it should be.

Strata:
  A colloquial  slang/spoken forms (model's own 'tricky' flags)  -> LLM-earns-place
  B polysemy    function words with many context senses          -> WSD / uncertainty
  C lowconf     ASR logprob tail                                   -> does confidence predict error
  D codeswitch  latin/cyrillic/numeric tokens inside AM text       -> loanword/NER failure mode
  E control     high-confidence ordinary words (random)            -> false-positive baseline
Plus PHRASE items: full-segment RU translation adequacy.
"""
import json, pathlib, re, random, argparse
from collections import Counter

HERE = pathlib.Path(__file__).resolve().parent.parent
corpus = json.loads((HERE / "data" / "corpus.json").read_text())
VIDEOS = {v["id"]: v for v in json.loads((HERE / "data" / "videos.json").read_text())}

ap = argparse.ArgumentParser()
ap.add_argument("--seed", type=int, default=20260808)
ap.add_argument("--A", type=int, default=35)
ap.add_argument("--B", type=int, default=25)
ap.add_argument("--C", type=int, default=35)
ap.add_argument("--D", type=int, default=20)
ap.add_argument("--E", type=int, default=25)
ap.add_argument("--phrases", type=int, default=20)
args = ap.parse_args()
rng = random.Random(args.seed)

def norm(t): return re.sub(r"[։՝՜՞,.\s]+", "", t).strip()
def has_latin(t): return bool(re.search(r"[A-Za-z]", t))
def has_cyr(t):   return bool(re.search(r"[А-Яа-яЁё]", t))
def has_num(t):   return bool(re.search(r"\d", t))

# colloquial / spoken forms to target (union of model 'notes' words + known slang)
COLLOQUIAL = set(map(norm, [
    "ջան","սենց","տենց","սաղ","էս","խի","խի՞","հլը","էլի","ա","չէ","բա",
    "հա","դե","նենց","էնպես","ոնց","ոնց՞","ապեր","ախպեր","տղա","չնաշ","մերսի",
]))
noted_forms = Counter()
for s in corpus:
    for n in s.get("notes", []):
        noted_forms[norm(n.get("word",""))] += 1
COLLOQUIAL |= {w for w,c in noted_forms.items() if c >= 3 and w}

# polysemous function words (from profiling): >=3 senses, high freq
form2gloss = {}
for s in corpus:
    for w in s.get("words", []):
        t, g = norm(w["text"]), (w.get("translation") or "").strip().lower()
        if t and g:
            form2gloss.setdefault(t, Counter())[g] += 1
POLYSEMOUS = {t for t,c in form2gloss.items() if len(c) >= 3 and sum(c.values()) >= 5}

# flatten word occurrences with full context
occ = []
for s in corpus:
    v = VIDEOS.get(s["video_id"], {})
    for wi, w in enumerate(s.get("words", [])):
        if not (w.get("text") and w.get("translation")):
            continue
        note = next((n for n in s.get("notes", [])
                     if norm(n.get("word","")) == norm(w["text"])), None)
        occ.append({
            "video_id": s["video_id"], "handle": s.get("handle"),
            "url": v.get("url"), "src": v.get("src"),
            "seg_index": s["seg_index"], "word_index": wi,
            "seg_text": s.get("text",""), "seg_explanation": s.get("explanation",""),
            "word": w["text"], "form": norm(w["text"]),
            "gloss": w["translation"], "logprob": w.get("logprob"),
            "start": w.get("start"), "end": w.get("end"),
            "note": (note or {}).get("note"), "note_gloss": (note or {}).get("gloss"),
        })

def key(o): return (o["video_id"], o["seg_index"], o["word_index"])
used = set()
def take(pool, k, stratum):
    rng.shuffle(pool)
    out = []
    seen_form = Counter()
    for o in pool:
        if key(o) in used:
            continue
        # cap repeats of the same word form so the sheet stays varied
        if seen_form[o["form"]] >= max(2, k // 8):
            continue
        o2 = dict(o); o2["stratum"] = stratum
        out.append(o2); used.add(key(o)); seen_form[o["form"]] += 1
        if len(out) >= k:
            break
    return out

A = take([o for o in occ if o["form"] in COLLOQUIAL or o["note"]], args.A, "A_colloquial")
B = take([o for o in occ if o["form"] in POLYSEMOUS and len(o["form"]) <= 4], args.B, "B_polysemy")
C = take([o for o in occ if isinstance(o["logprob"],(int,float)) and o["logprob"] < -0.4], args.C, "C_lowconf")
D = take([o for o in occ if has_latin(o["word"]) or has_cyr(o["word"]) or has_num(o["word"])], args.D, "D_codeswitch")
E = take([o for o in occ if isinstance(o["logprob"],(int,float)) and o["logprob"] > -0.02], args.E, "E_control")

items = A + B + C + D + E
for i, it in enumerate(items):
    it["id"] = f"w{i:03d}"

# annotate each item with the team's ASR-difficulty category (if the video is
# in videos_dataset/); enables gloss-accuracy-by-difficulty later. IDs are
# unchanged, so existing human labels remain valid.
try:
    from difficulty import video_to_category
    _v2c = video_to_category()
    for it in items:
        it["asr_difficulty"] = _v2c.get(it["video_id"])
except Exception as _e:
    for it in items:
        it.setdefault("asr_difficulty", None)

# phrase items: stratify across genres + include slang-heavy segments
segs = [s for s in corpus if s.get("explanation") and len(s.get("words",[]))>=3]
slangy = [s for s in segs if any(norm(w["text"]) in COLLOQUIAL for w in s["words"])]
plain  = [s for s in segs if s not in slangy]
rng.shuffle(slangy); rng.shuffle(plain)
phr_src = slangy[:args.phrases*2//3] + plain[:args.phrases - args.phrases*2//3]
phrases = []
for i, s in enumerate(phr_src[:args.phrases]):
    v = VIDEOS.get(s["video_id"], {})
    phrases.append({
        "id": f"p{i:03d}", "video_id": s["video_id"], "handle": s.get("handle"),
        "url": v.get("url"), "src": v.get("src"), "seg_index": s["seg_index"],
        "seg_text": s["text"], "explanation": s["explanation"],
        "start": s.get("start"), "end": s.get("end"),
    })

out = {"seed": args.seed, "counts": {k:len(v) for k,v in
        [("A",A),("B",B),("C",C),("D",D),("E",E),("phrases",phrases)]},
       "words": items, "phrases": phrases}
(HERE/"out"/"gold_items.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
print("strata:", out["counts"])
print(f"total word items: {len(items)}   phrase items: {len(phrases)}")
print("wrote out/gold_items.json")
