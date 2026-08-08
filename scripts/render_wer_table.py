#!/usr/bin/env python3
"""Render out/asr_wer_models.json into out/ASR_WER.md as a markdown table.
Run AFTER scripts/asr_wer_models.py, from the repo root."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
if not (HERE/"out").is_dir():
    HERE = Path(".")
SRC = HERE/"out"/"asr_wer_models.json"
if not SRC.is_file():
    raise SystemExit("ERROR: %s not found -- run scripts/asr_wer_models.py first." % SRC)

d = json.loads(SRC.read_text(encoding="utf-8"))
models = d.get("models", {})
if not models:
    raise SystemExit("ERROR: no models in %s" % SRC)

CATS = ["formal", "single_speaker", "multi_speakers", "songs", "difficult",
        "songs_difficult"]
present = [c for c in CATS
           if any(c in m.get("by_category", {}) for m in models.values())]
BIASED = {"elevenlabs_scribe_v2.basic"}
rows = sorted(models.items(), key=lambda kv: kv[1]["overall"]["WER"])

hdr = "| Model | " + " | ".join(c.replace("_", " ") for c in present) + \
      " | **ALL WER** | ALL CER |"
sep = "|---|" + "---|"*(len(present)+2)
md = ["# ASR word error rate vs human references", "",
      "Lower is better. `ALL WER` is the pooled word error rate across all",
      "scored clips; `ALL CER` the character error rate. Produced by",
      "`scripts/asr_wer_models.py` from `out/asr_refs.json`, rendered by",
      "`scripts/render_wer_table.py`.", "",
      "**Caveat:** the human references were created by correcting",
      "ElevenLabs Scribe's output in `eval/asr.html`, so Scribe (shown in",
      "italics) is scored against text derived from itself and its WER is",
      "biased low. Treat it as the anchor, not as a fair competitor.", "",
      hdr, sep]

for name, m in rows:
    cells = []
    for c in present:
        v = m.get("by_category", {}).get(c)
        cells.append("%.3f" % v["WER"] if v else "-")
    label = "*(%s)*" % name if name in BIASED else name
    md.append("| %s | %s | **%.3f** | %.3f |" % (
        label, " | ".join(cells), m["overall"]["WER"], m["overall"]["CER"]))

n = d.get("n_refs")
md += ["", "Scored on %s human-labeled reference segments." % (n if n else "?"),
       "", "Note: a model can score near 1.000 for two very different reasons --",
       "it transcribed into the wrong script entirely (Latin/Arabic/Devanagari),",
       "or it returned nothing. See `out/ASR_MODEL_QUALITY.md` for the",
       "coverage / loop / script breakdown that separates those cases."]

(HERE/"out"/"ASR_WER.md").write_text("\n".join(md)+"\n", encoding="utf-8")
print("wrote out/ASR_WER.md  (%d models, %d categories)" % (len(rows), len(present)))
for name, m in rows[:6]:
    print("  %-42s %.3f" % (name, m["overall"]["WER"]))
