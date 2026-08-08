#!/usr/bin/env python3
"""Consolidate every human annotation into ONE canonical gold dataset:
   out/gold_dataset.json  — single source of truth for judge validation + release.

Merges:
  gold_items.json    sampled items + metadata (stratum, asr_difficulty, logprob)
  gold_labels.json   per-word gloss verdicts / corrections / mis-transcribed flags
  sentence_refs.json sentence ratings + reference translations
  asr_refs.json      transcription references (WER ground truth)
Leaves a slot for the upcoming `grammar` annotation layer.
"""
import json, pathlib, datetime
HERE=pathlib.Path(__file__).resolve().parent.parent; O=HERE/"out"
def load(p, default=None):
    fp=O/p
    return json.loads(fp.read_text()) if fp.exists() else default

gi=load("gold_items.json",{"words":[],"phrases":[]})
gl=load("gold_labels.json",{}); gl=gl.get("labels",gl)
sr=load("sentence_refs.json",{}); sr=sr.get("sentences",{})
ar=load("asr_refs.json",{}); ar=ar.get("refs",{})
grammar=load("grammar_labels.json",{}); grammar=grammar.get("labels",grammar) if grammar else {}
asr_items={s["id"]:s for s in (load("asr_items.json",[]) or [])}

words=[]
for it in gi["words"]:
    h=gl.get(it["id"],{})
    words.append({
        "id":it["id"],"video_id":it["video_id"],"handle":it.get("handle"),
        "stratum":it.get("stratum"),"asr_difficulty":it.get("asr_difficulty"),
        "seg_text":it["seg_text"],"seg_translation":it.get("seg_explanation"),
        "word":it["word"],"model_gloss":it["gloss"],"logprob":it.get("logprob"),
        "model_note":it.get("note"),
        "human":{"verdict":h.get("verdict"),"correction":(h.get("correction") or "").strip(),
                 "mistranscribed":bool(h.get("mistranscribed"))},
        "grammar":grammar.get(it["id"]),           # filled by the grammar pass
    })

sentences=[]
for p in gi["phrases"]:
    r=sr.get(p["id"],{})
    sentences.append({"id":p["id"],"video_id":p["video_id"],"handle":p.get("handle"),
        "seg_text":p["seg_text"],"model_translation":p.get("explanation"),
        "human":{"rating":r.get("rating"),"reference":(r.get("reference") or "").strip()}})

asr_clips=[]
for cid,it in asr_items.items():
    r=ar.get(cid,{})
    if not r: continue
    asr_clips.append({"id":cid,"category":it.get("category"),"video_id":it.get("video_id"),
        "asr_text":it["text"],"human_reference":r.get("reference"),
        "unchanged":bool(r.get("unchanged"))})

def n_lab(xs,key): return sum(1 for x in xs if x["human"].get(key))
meta={"built":datetime.date.today().isoformat(),
      "words_total":len(words),
      "words_gloss_labeled":sum(1 for w in words if w["human"]["verdict"]),
      "words_grammar_labeled":sum(1 for w in words if w.get("grammar")),
      "sentences_rated":sum(1 for s in sentences if s["human"]["rating"]),
      "asr_clips_checked":len(asr_clips)}
out={"meta":meta,"words":words,"sentences":sentences,"asr_clips":asr_clips}
(O/"gold_dataset.json").write_text(json.dumps(out,ensure_ascii=False,indent=2))
print("consolidated gold ->", "out/gold_dataset.json")
for k,v in meta.items(): print(f"  {k}: {v}")
