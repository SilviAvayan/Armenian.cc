#!/usr/bin/env python3
"""Validate that a pipeline output file is eval-ready (see SCHEMA.md).
Accepts either a list[Segment] (one video) or the window.ALL_SEGMENTS / raw JSON
forms. Exits non-zero on hard errors; warns on soft issues.

Usage: python3 scripts/validate_pipeline_output.py path/to/segments.json [--id handle_123]
"""
import json, sys, re, argparse, pathlib

ap=argparse.ArgumentParser()
ap.add_argument("file")
ap.add_argument("--id", default=None, help="expected video id (mp4 stem) to check")
a=ap.parse_args()

raw=pathlib.Path(a.file).read_text()
try:
    data=json.loads(raw)
except json.JSONDecodeError:
    # tolerate `X = [...]` JS assignment forms
    i=raw.find("["); j=raw.rfind("]")
    data=json.loads(raw[i:j+1])

# normalize to list of segments
if isinstance(data,dict):
    if len(data)==1 and isinstance(next(iter(data.values())),list):
        data=next(iter(data.values()))
    elif "words" in data:
        data=[data]
if not isinstance(data,list):
    print("FAIL: expected a list of segments"); sys.exit(2)

errors=[]; warns=[]; nwords=0; ngloss=0; nlp=0; nnotes=0
for si,s in enumerate(data):
    where=f"seg[{si}]"
    for f in ("text","words","explanation"):
        if f not in s: errors.append(f"{where}: missing '{f}'")
    ws=s.get("words",[])
    if not isinstance(ws,list) or not ws:
        errors.append(f"{where}: 'words' must be a non-empty list"); continue
    for wi,w in enumerate(ws):
        nwords+=1
        if "text" not in w: errors.append(f"{where}.words[{wi}]: missing 'text'")
        if w.get("translation"): ngloss+=1
        lp=w.get("logprob")
        if isinstance(lp,(int,float)):
            nlp+=1
            if lp>0.0001: warns.append(f"{where}.words[{wi}]: logprob {lp} > 0 (expect log-prob ≤ 0)")
    nnotes+=len(s.get("notes",[]) or [])

if nwords:
    if ngloss/nwords < 0.9: errors.append(f"only {ngloss}/{nwords} words have 'translation' (need ≥90%)")
    if nlp/nwords   < 0.9: warns.append(f"only {nlp}/{nwords} words have 'logprob' — uncertainty eval will be limited")
if a.id and not re.match(r"^[A-Za-z0-9._]+_\d+$", a.id):
    warns.append(f"id '{a.id}' doesn't match handle_videoid pattern; difficulty join may fail")

print(f"segments={len(data)} words={nwords} with_gloss={ngloss} with_logprob={nlp} notes={nnotes}")
for w in warns[:20]: print("  WARN:",w)
for e in errors[:20]: print("  ERROR:",e)
if errors:
    print(f"\n✗ NOT eval-ready: {len(errors)} error(s)"); sys.exit(1)
print("\n✓ eval-ready" + (f" ({len(warns)} warning(s))" if warns else ""))
