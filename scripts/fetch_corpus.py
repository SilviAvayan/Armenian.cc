#!/usr/bin/env python3
"""Fetch the full armenian.cc corpus (video index + per-video segments).

Output:
  data/videos.json           normalized list of video metadata
  data/segments/<segKey>.json  per-video list of segments (transcript+gloss)
  data/corpus.json           one flat file: every segment with its video id
"""
import json, re, sys, time, urllib.request, pathlib

BASE = "https://armenian.cc"
HERE = pathlib.Path(__file__).resolve().parent.parent
DATA = HERE / "data"
SEG_DIR = DATA / "segments"
SEG_DIR.mkdir(parents=True, exist_ok=True)

UA = {"User-Agent": "Mozilla/5.0 (armenian-eval research)"}

def get(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")

def strip_assign(js: str) -> str:
    """Turn `window.X = <json>;` or `(window.X=...)['k'] = <json>;` into JSON.

    The value is whatever follows the last `=` that sits at bracket-depth 0
    and outside any string — that skips the inner `=` in the ALL_SEGMENTS guard.
    """
    depth = 0
    in_str = None
    last_eq = -1
    prev = ""
    for idx, ch in enumerate(js):
        if in_str:
            if ch == in_str and prev != "\\":
                in_str = None
        elif ch in "\"'":
            in_str = ch
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "=" and depth == 0:
            last_eq = idx
        prev = ch
    body = js[last_eq + 1:]
    body = body.strip().rstrip(";").strip()
    return body

def main():
    print("· fetching video index …")
    vjs = get(f"{BASE}/data_processed/videos.js?v=1")
    videos = json.loads(strip_assign(vjs))
    (DATA / "videos.json").write_text(json.dumps(videos, ensure_ascii=False, indent=2))
    print(f"  {len(videos)} videos")

    corpus = []
    for n, v in enumerate(videos, 1):
        seg_key = v["segKey"]
        seg_ver = v.get("segVer", "1")
        url = f"{BASE}/data_processed/segments_{seg_key}.js?v={seg_ver}"
        try:
            sjs = get(url)
            segs = json.loads(strip_assign(sjs))
        except Exception as e:
            print(f"  ! {seg_key}: {e}")
            continue
        (SEG_DIR / f"{seg_key}.json").write_text(
            json.dumps(segs, ensure_ascii=False, indent=2))
        for si, s in enumerate(segs):
            corpus.append({
                "video_id": v["id"],
                "handle": v.get("handle"),
                "published": v.get("published"),
                "seg_index": si,
                **s,
            })
        print(f"  [{n}/{len(videos)}] {seg_key}: {len(segs)} segments")
        time.sleep(0.15)

    (DATA / "corpus.json").write_text(
        json.dumps(corpus, ensure_ascii=False, indent=2))
    n_words = sum(len(s.get("words", [])) for s in corpus)
    n_notes = sum(len(s.get("notes", [])) for s in corpus)
    print(f"\n✓ corpus: {len(corpus)} segments, {n_words} words, {n_notes} notes")

if __name__ == "__main__":
    main()
