# armenian.cc — LLM evaluation harness

Evaluates the LLM pipeline behind [armenian.cc](https://armenian.cc): viral Armenian
TikToks → **ElevenLabs** speech recognition → **Gemini** per-word Russian glosses,
full-sentence translations, and grammar notes, for Russian speakers learning spoken Armenian.

The goal is not to assert "it works" but to **measure** it against a fluent-human gold
standard: where it's accurate, where it breaks, whether the shipped ASR confidence predicts
errors, whether an LLM judge can be trusted to scale, and which model to actually ship.

## Pipeline
```
video → ASR (ElevenLabs Scribe)      speech_recognition/video_transcribe.py
      → words→segments bridge         scripts/asr_to_segments.py
      → translate (sentence + gloss)  scripts/translate.py
      → EVALUATION                    scripts/*.py  (this harness)
```
The ASR stage emits Scribe's per-word data (`text,start,end,logprob`) — the uncertainty
analysis and word↔gloss alignment depend on `logprob`. Any pipeline that emits the
per-segment JSON in [SCHEMA.md](SCHEMA.md) drops straight into the eval
(`scripts/validate_pipeline_output.py` checks conformance).

## Headline findings (all human-anchored)

| stage | result |
|---|---|
| **ASR** (ElevenLabs Scribe) | **7.6% WER** overall — best of a 33-model benchmark; 0% formal → ~22% on hard speech. Confidence and WER rank difficulty identically (ρ=1.0). |
| **Per-word gloss** (live product) | **88% correct in context** (95% CI 81–93%, n=113; 94% allowing near-synonyms). Weakest where the audio is least confident. |
| **Sentence translation** | **90% faithful** (human direct assessment). |
| **Translation model bake-off** | **`gemini-3.1-flash-lite` wins** — chrF++ 71.7, 100% valid, 1.5s. Reasoning/pro tiers match quality but cost 4–10× latency; `deepseek-v4-flash` is worst (40.0) and ~30× slower. See `results/model_bakeoff.json`. |
| **Uncertainty** | Shipped ASR log-prob predicts errors: **AUC 0.86** (mis-hear), **0.69** (gloss error). 29% of gloss errors trace to ASR mis-hearing, not translation. |
| **LLM-as-judge** | Zero-shot judges fail (gloss κ=0.22 over-flags; grammar κ=0.00 rubber-stamps). **Few-shot with 8 human examples lifts the gloss judge to κ=0.66** — the human labels make the judge trustworthy. |
| **Named failure** | *Copula/auxiliary gloss contamination* — the auxiliary «է/եմ» absorbs a neighbouring word's meaning (`scripts/copula_probe.py`). |

Full numbers, charts, and the narrative are in **[results/REPORT.md](results/REPORT.md)**.

## Human annotations — `gold/`

The ground truth everything is measured against, hand-labeled by a fluent Armenian/Russian
speaker. This is the anchor of the whole eval — versioned so every number is reproducible.

| file | what it is |
|---|---|
| `gold/gold_labels.json` | **130 per-word gloss verdicts** (correct / acceptable / wrong / unsure) + corrections + a "mis-transcribed" flag that separates ASR blame from translation blame. |
| `gold/sentence_refs.json` | **20 full-sentence** faithfulness ratings + reference translations. |
| `gold/note_labels.json` | **50 grammar/etymology note verdicts** (is the model's linguistic claim true?). Rule applied: a left comment ⇒ the note is wrong. `note_labels.raw.json` is the untouched export. |
| `gold/asr_refs.json` | **25 human-corrected transcripts** — the WER ground truth (ElevenLabs output fixed to what is actually said). |
| `gold/gold_dataset.json` | Consolidated single source of truth (all of the above joined by item id). |

Sampling is **stratified and adversarial** (colloquial/slang, polysemy, low-confidence audio,
code-switch, + an easy control) so the labeler's time stresses the hard cases, with a control
stratum to measure false-alarm rates. Re-generate the blind labeling tools with
`scripts/build_*_tool.py` (`eval/label.html`, `eval/sentences.html`, `eval/notes.html`).

## Results — `results/`

Derived metrics + report, regenerated from `gold/` by the scripts:
`model_bakeoff.json` (translation leaderboard), `results.json` (gloss accuracy by stratum,
Wilson CIs, uncertainty AUC), `asr_wer.json`, `asr_difficulty.json`, `sentence_eval.json`,
`reproduction_eval.json`, `note_judge_validation.json`, `fewshot_judge.json`,
`copula_probe.json`, `failures.json`, plus `REPORT.md` and `chart_*.svg`.

## Run
```bash
./run_all.sh --mock     # full pipeline on synthetic labels, no key (sanity check)
./run_all.sh            # offline metrics from gold/  (no key)
./run_all.sh --llm      # + live judge + context/no-context baseline (needs key)
```
Model runs use OpenRouter (`OPENROUTER_API_KEY` in `.env`, gitignored). The judge is
**cross-family** (DeepSeek, not the Gemini being judged) and only trusted after it agrees
with `gold/`. Everything up to the human labels is seeded and regenerates deterministically.

## Layout
```
gold/            human annotations (ground truth) — see above
results/         derived metrics, REPORT.md, charts
scripts/         fetch, sample, label-tools, analyze, LLM harness (judge/baseline/bakeoff), charts, report
eval/            blind labeling tools (label.html, sentences.html, notes.html)
data/            scraped corpus (gitignored; re-fetch: scripts/fetch_corpus.py)
SCHEMA.md        pipeline-output contract + validator
.env             OPENROUTER_API_KEY (gitignored)
```
