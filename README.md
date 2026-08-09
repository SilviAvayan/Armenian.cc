# armenian.cc — evaluation harness

Evaluates the pipeline behind [armenian.cc](https://armenian.cc): viral Armenian
TikToks → **ElevenLabs** ASR → **Gemini** per-word Russian glosses, full-phrase
translations, and linguistic notes, for Russian speakers learning spoken Armenian.

The goal is not to assert "it works" but to **measure** it: where it's accurate,
where it breaks, whether its shipped confidence signal predicts errors, and whether
the LLM is doing work a dictionary couldn't.

Two tracks live here:

1. **ASR model comparison** — which speech-to-text model to use for Armenian.
   Results are committed; see [ASR_EVALUATION.md](ASR_EVALUATION.md).
2. **Pipeline evaluation harness** — gloss/translation accuracy, uncertainty,
   failure taxonomy. Code is committed; outputs regenerate locally (see *Run*).

**Headline result — [ASR model comparison](ASR_EVALUATION.md):** 36 transcription
runs across 33 distinct models (ElevenLabs, Gemini, OpenAI, Whisper, Chirp, Deepgram,
…) scored against human-corrected references. ElevenLabs Scribe v1 leads
(WER 0.061); Gemini is the only competitive LLM family (best `gemini-3-flash-preview`,
0.104); the commodity ASR stack is currently unusable for Armenian, mostly above
0.5 WER.

**Headline result — translation & glossing:** on a fluent-human gold set, per-word
glosses are **88% correct in context** (95% CI 81–93%, n=113; 94% allowing
near-synonyms) and full sentences **90% faithful**. An 11-model translation bake-off
picks **`gemini-3.1-flash-lite`** (chrF++ 71.7, 100% valid output, 1.5 s) — the
reasoning/pro tiers match quality but cost 4–10× the latency (`results/model_bakeoff.json`).
Off-the-shelf LLM judges are unreliable (gloss κ 0.22, grammar κ 0.00), but **few-shot
with 8 human examples lifts the gloss judge to κ 0.66** — the human labels make the
judge trustworthy. Full numbers in **[results/REPORT.md](results/REPORT.md)**.

## Pipeline
The ASR stage **must emit Scribe's per-word data** (`text,start,end,logprob`), not just
plain text — the uncertainty analysis and word/gloss alignment depend on `logprob`.
`asr_to_segments.py` groups those words into sentence segments; `translate.py` adds the
full-sentence translation + per-word contextual gloss + notes (eval-ready, see
[SCHEMA.md](SCHEMA.md)).

## The benchmark set

`dataset/videos.json` — 19 TikTok videos with `id`, `handle`, `url`, `category`,
hand-rated into five difficulty categories: `formal` (3), `single_speaker` (4),
`multi_speakers` (5), `songs` (4), `difficult` (3). ~20 min of audio.

`dataset/transcripts/<model>.<variant>/<category>/<video_id>.{txt,json}` — one folder
per run. Variants: `.basic` (33), plus `google_chirp_3.chunked`,
`openai_gpt_transcribe.tuned`, and `elevenlabs_scribe_v2_realtime.hye`.

> **Note:** `elevenlabs_scribe_v2.basic` is the odd one out — it holds 111 transcripts
> across six categories (it includes an extra `songs_difficult` folder), because it is
> the production baseline run over the wider corpus rather than just the 19-clip
> benchmark. Every other folder is the 19-clip set. Scoring in `ASR_EVALUATION.md`
> uses only the 19-clip subset.

Provenance of each folder, known blemishes, and per-model costs are documented at the
bottom of [ASR_EVALUATION.md](ASR_EVALUATION.md).

## What the harness measures
1. **Per-word gloss accuracy** on a *stratified* human-gold set (colloquial, polysemy,
   low-confidence, code-switch, and an easy control), with Wilson 95% CIs.
2. **"LLM earns its place"** — a controlled context-vs-no-context experiment: the same
   model glossing each word with and without its sentence. The gap is the value of context.
3. **ASR quality by difficulty** — joins hand-rated difficulty categories onto
   ElevenLabs' shipped per-word confidence. No re-transcription: shows confidence
   degrades monotonically with rated difficulty.
4. **Uncertainty** — does the pipeline's per-word ASR log-prob actually predict errors?
   (ROC-AUC + a flag with measured precision/recall.) Also separates ASR vs translation blame.
5. **LLM-as-judge**, cross-family (DeepSeek, not Gemini) and **validated against the human
   labels** (Cohen's κ) before being trusted to scale.
6. **Failure taxonomy + safety** — categorized real failures and who they could harm.

The eval consumes the site's existing per-segment JSON shape — see [SCHEMA.md](SCHEMA.md)
and `scripts/validate_pipeline_output.py` so a teammate's pipeline output drops straight in.

## Human annotations — `gold/`

The ground truth everything is measured against, hand-labeled by a fluent Armenian/Russian
speaker and **committed** so every number is reproducible. This is the anchor of the eval.

| file | what it is |
|---|---|
| `gold/gold_labels.json` | **130 per-word gloss verdicts** (correct / acceptable / wrong / unsure) + corrections + a "mis-transcribed" flag that separates ASR blame from translation blame. |
| `gold/sentence_refs.json` | **20 full-sentence** faithfulness ratings + reference translations. |
| `gold/note_labels.json` | **50 grammar/etymology note verdicts** (is the model's linguistic claim true?). Rule: a left comment ⇒ the note is wrong. `note_labels.raw.json` is the untouched export. |
| `gold/asr_refs.json` | **25 human-corrected transcripts** — the WER ground truth. |
| `gold/gold_dataset.json` | Consolidated single source of truth (all of the above, joined by item id). |

Sampling is **stratified and adversarial** (colloquial/slang, polysemy, low-confidence
audio, code-switch, + an easy control) so the labeler's time stresses the hard cases,
with a control stratum to measure false-alarm rates.

## Results — `results/`

Derived metrics + report, **committed**, regenerated from `gold/` by the scripts:
`model_bakeoff.json` (translation leaderboard), `results.json` (gloss accuracy by stratum
+ Wilson CIs + uncertainty AUC), `asr_wer.json`, `asr_difficulty.json`, `sentence_eval.json`,
`reproduction_eval.json`, `note_judge_validation.json`, `fewshot_judge.json`,
`copula_probe.json`, `failures.json`, plus `REPORT.md` and `chart_*.svg`.

## Layout
`gold/` human annotations (committed) · `results/` derived metrics + REPORT (committed) ·
`scripts/` harness (fetch, sample, label-tools, analyze, judge/baseline/bakeoff, charts) ·
`eval/` blind labeling tools · `SCHEMA.md` pipeline contract · `LICENSE.md`.

**Not in the repo** (gitignored or external, expected locally):
`data/` scraped corpus — re-fetch with `scripts/fetch_corpus.py`;
`out/*` scratch analysis artifacts — regenerate with `./run_all.sh` (committed snapshots
live in `results/` and `gold/`);
`videos_dataset/` source audio — external folder, path set by `$VIDEOS_DATASET`
(defaults to a hardcoded local path in `scripts/difficulty.py`); steps that need it
skip cleanly when it's absent.

## Run
```bash
./run_all.sh --mock     # full pipeline on synthetic labels, no key (sanity check)
./run_all.sh            # offline metrics from gold/ (no key)
./run_all.sh --llm      # + live judge + context/no-context baseline (needs key)
```
Judge/system models default to `deepseek/deepseek-chat-v3.1`; override with
`JUDGE=` and `SYS=` environment variables. Live runs need `OPENROUTER_API_KEY`.

Reproduce the ASR WER table (needs your exported references):
```bash
python3 scripts/asr_wer_models.py --refs <path-to>/asr_refs.json
```

Labeling: open the relevant `eval/*.html`, judge each item, **Export** → drop the file
at the path above. Blind by design (the labeler never sees the model's confidence
or which stratum an item came from).

Everything up to the human labels is seeded and regenerates deterministically.

## Caveats worth reading before quoting numbers
- The WER table is **n = 25 segments (~700 reference words)**. Tiers are meaningful;
  differences of a few points between adjacent rows are not.
- References were produced by **correcting ElevenLabs output**, giving ElevenLabs rows
  a home-field advantage of unknown size.
- `out/ASR_MODEL_QUALITY.md` numbers are **ground-truth-free** — coverage, empty rate,
  loop rate, script correctness. They are not accuracy.
- Metrics quoted in `PITCH_BRIEF.md` are mirrored in the **committed** `results/REPORT.md`
  and `results/*.json`; `out/` is scratch. They regenerate from `gold/` via `./run_all.sh`.
- The translation gold set is **n = 113 labeled words / 20 sentences** — tiers and large
  gaps are meaningful; adjacent one-point differences are not.

## License
Apache License 2.0 — see [LICENSE.md](LICENSE.md).
