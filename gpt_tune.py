#!/usr/bin/env python3
"""Best-effort openai/gpt-transcribe pass over the 19-clip set, with the full
playbook learned from chirp: quality gates (loop / impossible-rate / wrong-script),
retry-on-empty, format ladder, temperature control, and chunked rescue.
Writes a NEW dir dataset/transcripts/openai_gpt_transcribe.tuned/ + ~/Downloads/gpt_tuned_results.json.
Run from the repo root:  export OPENROUTER_API_KEY="sk-or-..."  then  python3 gpt_tune.py"""
import base64, collections, json, os, re, shutil, subprocess, sys, time
from pathlib import Path
import requests

MODEL = "openai/gpt-transcribe"
URL = "https://openrouter.ai/api/v1/audio/transcriptions"
AUDIO = Path.home()/"Downloads"/"arm_audio"
SEGS = Path.home()/"Downloads"/"chirp_kit"/"chirp_audio"
WAVD = Path.home()/"Downloads"/"gpt_tune_wav"
OUTJ = Path.home()/"Downloads"/"gpt_tuned_results.json"
ROOT = Path("dataset/transcripts/openai_gpt_transcribe.tuned")
TIMEOUT = 240
TRIES = 3
SLEEP = 3.0

def die(m):
    raise SystemExit("ERROR: " + m)

if not Path(".git").is_dir():
    die("run from the repo root (no .git here).")
KEY = os.environ.get("OPENROUTER_API_KEY") or die("export OPENROUTER_API_KEY first")
if not AUDIO.is_dir():
    die("%s not found" % AUDIO)

def degenerate(t, dur):
    letters = re.findall(u"[A-Za-z\u0400-\u04FF\u0530-\u058F\u0600-\u06FF\u0900-\u097F]", t)
    if len(letters) >= 5:
        arm = sum(1 for c in letters if u"\u0530" <= c <= u"\u058F")
        if arm/len(letters) < 0.5:
            return "wrong script (%d%% Armenian)" % (100*arm//len(letters))
    w = t.split()
    if dur > 3 and len(w)/dur > 6.0:
        return "impossible rate %.1f w/s" % (len(w)/dur)
    if len(w) >= 20:
        g = collections.Counter(tuple(w[i:i+5]) for i in range(len(w)-4))
        c = g.most_common(1)[0][1]
        if c >= 15 and c*5/len(w) > 0.6:
            return "loop x%d" % c
    return None

def to_wav(src):
    WAVD.mkdir(exist_ok=True)
    dst = WAVD/(src.stem + ".wav")
    if dst.is_file() and dst.stat().st_size:
        return dst
    if shutil.which("ffmpeg"):
        cmd = ["ffmpeg","-y","-i",str(src),"-ac","1","-ar","16000",str(dst),"-loglevel","error"]
    elif shutil.which("afconvert"):
        cmd = ["afconvert","-f","WAVE","-d","LEI16",str(src),str(dst)]
    else:
        return None
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError:
        return None
    return dst if dst.is_file() and dst.stat().st_size else None

B64 = {}
def b64(p):
    if p not in B64:
        B64[p] = base64.b64encode(p.read_bytes()).decode()
    return B64[p]

def post(b, fmt, temp):
    payload = {"model": MODEL, "input_audio": {"data": b, "format": fmt},
               "language": "hy", "temperature": temp}
    last = ""
    for a in (1, 2):
        t0 = time.perf_counter()
        try:
            r = requests.post(URL, headers={"Authorization": "Bearer "+KEY,
                                            "Content-Type": "application/json"},
                              data=json.dumps(payload), timeout=TIMEOUT)
        except requests.RequestException as e:
            last = "request failed: %s" % e
        else:
            lat = time.perf_counter()-t0
            if r.status_code == 200:
                try:
                    body = r.json()
                except ValueError:
                    return {"ok": False, "error": "non-JSON", "latency": lat}
                u = body.get("usage", {}) or {}
                return {"ok": True, "latency": lat,
                        "text": (body.get("text") or "").strip(),
                        "cost": u.get("cost"), "audio_seconds": u.get("seconds")}
            last = "HTTP %d: %s" % (r.status_code, r.text[:200])
            if r.status_code not in (408,429,500,502,503,504):
                return {"ok": False, "error": last, "latency": lat}
        if a == 1:
            time.sleep(2)
    return {"ok": False, "error": last, "latency": 0.0}

def run_clip(path, dur):
    attempts = []
    rungs = [("m4a:t0", path, "m4a", 0.0)]
    w = to_wav(path)
    if w:
        rungs.append(("wav:t0", w, "wav", 0.0))
    rungs.append(("m4a:t0.4", path, "m4a", 0.4))
    for name, p, fmt, temp in rungs:
        for t in range(1, TRIES+1):
            r = post(b64(p), fmt, temp)
            rec = {"variant": name, "try": t, "ok": r.get("ok"),
                   "chars": len(r.get("text","")), "error": r.get("error")}
            if r.get("ok") and r.get("text"):
                bad = degenerate(r["text"], dur)
                if bad:
                    rec["rejected"] = bad
                    attempts.append(rec)
                    time.sleep(SLEEP)
                    continue
                attempts.append(rec)
                return {"text": r["text"], "variant": name, "attempts": attempts,
                        "cost": r.get("cost"), "latency": r.get("latency"),
                        "audio_seconds": r.get("audio_seconds"), "chunked": False}
            attempts.append(rec)
            if not r.get("ok"):
                break
            time.sleep(SLEEP)
    stem = path.stem
    parts = sorted(SEGS.glob(stem + "__part*.m4a")) if SEGS.is_dir() else []
    parts = [p for p in parts if "__norm" not in p.name]
    if len(parts) > 1:
        texts = []
        for p in parts:
            best = ""
            for t in range(1, TRIES+1):
                r = post(b64(p), "m4a", 0.0)
                ok = r.get("ok") and r.get("text") and not degenerate(r["text"], 60)
                attempts.append({"variant": "seg:"+p.stem[-6:], "try": t,
                                 "ok": r.get("ok"), "chars": len(r.get("text",""))})
                if ok:
                    best = r["text"]
                    break
                if not r.get("ok"):
                    break
                time.sleep(SLEEP)
            if best:
                texts.append(best)
        if texts:
            return {"text": " ".join(texts).strip(), "variant": "chunked-rescue",
                    "attempts": attempts, "cost": None, "latency": None,
                    "audio_seconds": None, "chunked": True}
    return {"text": "", "variant": "exhausted", "attempts": attempts,
            "cost": None, "latency": None, "audio_seconds": None, "chunked": False}

clips = sorted(AUDIO.glob("*.m4a"))
if not clips:
    die("no .m4a files in %s" % AUDIO)
results = {}
if OUTJ.is_file():
    try:
        results = json.loads(OUTJ.read_text(encoding="utf-8"))
    except Exception:
        results = {}

print("clips:", len(clips))
for i, p in enumerate(clips, 1):
    stem = p.stem
    if "__" not in stem:
        continue
    cat, clip = stem.split("__", 1)
    prev = results.get(stem)
    if prev and prev.get("text"):
        print("[%d/%d] %s -- kept (already good)" % (i, len(clips), stem[:50]))
        continue
    dur = 0.0
    try:
        pr = subprocess.run(["afinfo", str(p)], capture_output=True, text=True)
        m = re.search(r"estimated duration: ([\d.]+)", pr.stdout)
        if m:
            dur = float(m.group(1))
    except Exception:
        pass
    print("[%d/%d] %s" % (i, len(clips), stem[:56]))
    r = run_clip(p, dur)
    tag = "ok via %s" % r["variant"] if r["text"] else "EMPTY after full ladder"
    print("      %s (%d attempts)" % (tag, len(r["attempts"])))
    results[stem] = {"category": cat, "clip": clip, "duration": dur}
    results[stem].update(r)
    OUTJ.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

n = 0
for stem, v in results.items():
    cat, clip = v["category"], v["clip"]
    d = ROOT/cat
    d.mkdir(parents=True, exist_ok=True)
    text = v["text"]
    (d/(clip+".txt")).write_text(text+"\n", encoding="utf-8")
    payload = {"source": clip+".mp4", "model": MODEL, "requested_language": "hy",
               "endpoint": "openrouter /v1/audio/transcriptions",
               "method": "temperature-0 + format ladder + retry-on-empty + quality gates (loop/rate/script) + chunked rescue",
               "duration_seconds": v.get("duration"), "ok": bool(text), "text": text,
               "variant": v.get("variant"),
               "chunks": [{"index": 1, "offset": 0.0, "text": text,
                           "usage": {"audio_seconds": v.get("audio_seconds"),
                                     "cost": v.get("cost")},
                           "latency_seconds": v.get("latency"),
                           "provider_model": MODEL}]}
    if not text:
        payload["note"] = "empty/degenerate on every rung incl. chunked rescue"
    (d/(clip+".json")).write_text(json.dumps(payload, ensure_ascii=False, indent=2)+"\n",
                                  encoding="utf-8")
    n += 1
with_text = sum(1 for v in results.values() if v["text"])
print("\nwrote %d clips under %s  (with text: %d)" % (n, ROOT, with_text))
