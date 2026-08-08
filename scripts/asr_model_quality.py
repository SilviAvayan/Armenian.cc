#!/usr/bin/env python3
"""Ground-truth-free ASR quality metrics for every model dir under
dataset/transcripts/<model>/<category>/<id>.txt, on the shared benchmark clips.

NOT accuracy numbers -- no human references are used:
  coverage      clips with non-empty transcript / clips present
  empty_rate    share of clips with an empty transcript
  loop_rate     share whose transcript is a degenerate repetition loop
                (one 5-gram repeated >=15x covering >60% of words; song
                choruses pass this test)
  armenian_pct  % of alphabetic chars in Armenian script (models that
                transliterate into Latin/Arabic/Devanagari score ~0 and are
                unusable for glossing regardless of acoustic accuracy)
  vs_scribe     MEDIAN per-clip word-level Levenshtein distance to
                elevenlabs_scribe_v2.basic, the production baseline.
                Scribe is NOT ground truth (its own committed transcript for
                difficult/www.ishkhanutyun is a repetition loop). 0 = reads
                like production; higher = different, not necessarily worse.

Real WER requires labeling eval/asr.html -> out/asr_refs.json, then
scripts/asr_wer_models.py.

Writes out/asr_model_quality.json and out/ASR_MODEL_QUALITY.md.
Run from the repo root:  python3 scripts/asr_model_quality.py
"""
import json, os, re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
if not (HERE/"dataset"/"transcripts").is_dir():
    HERE = Path(".")
TR = HERE/"dataset"/"transcripts"
ANCHOR = "elevenlabs_scribe_v2.basic"

if not TR.is_dir():
    raise SystemExit("ERROR: no dataset/transcripts here -- cd to the repo root.")

ref_dir = None
for cand in ("google_chirp_3.chunked", "openai_gpt_transcribe.basic", ANCHOR):
    if (TR/cand).is_dir():
        ref_dir = TR/cand
        break
BENCH = sorted((p.parent.name, p.stem) for p in ref_dir.glob("*/*.txt"))

def norm(t):
    return re.sub(u"[\u0589\u055d\u055c\u055b'\u2019,.\\-\u2014\u00ab\u00bb\u2026:;!?]", " ",
                  (t or "").lower()).replace(u"\u0565\u0582", u"\u0587")

def toks(t):
    return norm(t).split()

def lev(a, b):
    n, m = len(a), len(b)
    prev = list(range(m+1))
    for i in range(1, n+1):
        cur = [i]+[0]*m
        for j in range(1, m+1):
            cur[j] = min(prev[j]+1, cur[j-1]+1, prev[j-1]+(a[i-1] != b[j-1]))
        prev = cur
    return prev[m]

def is_loop(t):
    w = t.split()
    if len(w) < 20:
        return False
    g = Counter(tuple(w[i:i+5]) for i in range(len(w)-4))
    c = g.most_common(1)[0][1]
    return c >= 15 and (c*5)/len(w) > 0.6

def armenian_pct(t):
    arm = len(re.findall(u"[\u0530-\u058F]", t))
    oth = len(re.findall(u"[A-Za-z\u0400-\u04FF\u0600-\u06FF\u0900-\u097F]", t))
    return 100.0*arm/(arm+oth) if (arm+oth) else None

anchor = {}
for cat, clip in BENCH:
    f = TR/ANCHOR/cat/(clip+".txt")
    if f.is_file():
        anchor[(cat, clip)] = f.read_text(encoding="utf-8").strip()

out = {"benchmark_clips": len(BENCH), "anchor": ANCHOR, "models": {}}
rows = []
for tdir in sorted(d for d in TR.iterdir() if d.is_dir()):
    present = texts = loops = 0
    arm_n = arm_d = 0.0
    dists = []
    clips = []
    for cat, clip in BENCH:
        f = tdir/cat/(clip+".txt")
        if not f.is_file():
            continue
        present += 1
        t = f.read_text(encoding="utf-8").strip()
        e = {"clip": cat+"/"+clip, "chars": len(t)}
        if not t:
            e["empty"] = True
        else:
            texts += 1
            if is_loop(t):
                loops += 1
                e["loop"] = True
            ap = armenian_pct(t)
            if ap is not None:
                e["armenian_pct"] = round(ap, 1)
                arm_n += ap
                arm_d += 1
            ref = anchor.get((cat, clip))
            if ref and tdir.name != ANCHOR:
                ra = toks(ref)
                e["scribe_dist"] = round(lev(ra, toks(t))/max(1, len(ra)), 3)
                dists.append(e["scribe_dist"])
        clips.append(e)
    if not present:
        continue
    st = {"clips_present": present,
          "coverage": round(texts/present, 3),
          "empty_rate": round((present-texts)/present, 3),
          "loop_rate": round(loops/present, 3),
          "armenian_pct": round(arm_n/arm_d, 1) if arm_d else None,
          "vs_scribe_median": round(sorted(dists)[len(dists)//2], 3) if dists else None,
          "clips": clips}
    out["models"][tdir.name] = st
    rows.append((tdir.name, st))

rows.sort(key=lambda r: (-r[1]["coverage"],
                         r[1]["vs_scribe_median"] if r[1]["vs_scribe_median"] is not None else 9))
hdr = "%-38s %3s %7s %7s %7s %7s %10s" % ("model", "n", "cover", "empty", "loops", "arm%", "vs-scribe")
print(hdr)
print("-"*len(hdr))
for name, s in rows:
    print("%-38s %3d %7.2f %7.2f %7.2f %7s %10s" % (
        name, s["clips_present"], s["coverage"], s["empty_rate"], s["loop_rate"],
        s["armenian_pct"] if s["armenian_pct"] is not None else "-",
        s["vs_scribe_median"] if s["vs_scribe_median"] is not None else "-"))

(HERE/"out").mkdir(exist_ok=True)
(HERE/"out"/"asr_model_quality.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")

md = ["# ASR model quality (ground-truth-free)", "",
      "Benchmark: %d clips. No human references were used, so these are NOT" % len(BENCH),
      "accuracy numbers. `vs-scribe` is the median per-clip word-distance to",
      "`elevenlabs_scribe_v2.basic` (production baseline, itself imperfect --",
      "its committed `difficult/www.ishkhanutyun` transcript is a repetition loop).",
      "For real WER: label `eval/asr.html` -> `out/asr_refs.json` ->",
      "`scripts/asr_wer_models.py`.", "",
      "| model | n | coverage | empty | loops | armenian % | vs-scribe (median) |",
      "|---|---|---|---|---|---|---|"]
for name, s in rows:
    md.append("| %s | %d | %.2f | %.2f | %.2f | %s | %s |" % (
        name, s["clips_present"], s["coverage"], s["empty_rate"], s["loop_rate"],
        s["armenian_pct"] if s["armenian_pct"] is not None else "-",
        s["vs_scribe_median"] if s["vs_scribe_median"] is not None else "-"))
md += ["", "`loops` counts committed transcripts that are decoder repetition",
       "loops, not transcriptions. `armenian %` near 0 means the model wrote",
       "the wrong script entirely (Latin / Arabic / Devanagari)."]
(HERE/"out"/"ASR_MODEL_QUALITY.md").write_text("\n".join(md)+"\n", encoding="utf-8")
print("\nwrote out/asr_model_quality.json and out/ASR_MODEL_QUALITY.md")
