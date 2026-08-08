# armenian.cc — LLM evaluation harness

Evaluates the LLM pipeline behind [armenian.cc](https://armenian.cc): viral Armenian
TikToks → **ElevenLabs** ASR → **Gemini** per-word Russian glosses, full-phrase
translations, and linguistic notes, for Russian speakers learning spoken Armenian.

The goal is not to assert "it works" but to **measure** it: where it's accurate,
where it breaks, whether its shipped confidence signal predicts errors, and whether
the LLM is doing work a dictionary couldn't.

**Headline result — [ASR model comparison](ASR_EVALUATION.md):** 36 transcription runs
across 33 models (ElevenLabs, Gemini, OpenAI, Whisper, Chirp, …) scored against
human-corrected references. ElevenLabs Scribe v1 leads (WER 0.061); Gemini is the only
competitive LLM family; commodity ASR fails on Armenian.

## Pipeline
```
video → ASR (ElevenLabs Scribe)      speech_recognition/video_transcribe.py  [teammate]
      → words→segments bridge         scripts/asr_to_segments.py
      → translate (sentence + gloss)  scripts/translate.py
      → EVALUATION                    scripts/analyze.py … (this harness)
```
The ASR stage **must emit Scribe's per-word data** (`text,start,end,logprob`), not just
plain text — the uncertainty analysis and word/gloss alignment depend on `logprob`.
`asr_to_segments.py` groups those words into sentence segments; `translate.py` adds the
full-sentence translation + per-word contextual gloss + notes (eval-ready, see SCHEMA.md).

## What it measures
1. **Per-word gloss accuracy** on a *stratified* human-gold set (colloquial, polysemy,
   low-confidence, code-switch, and an easy control), with Wilson 95% CIs.
2. **"LLM earns its place"** — a controlled context-vs-no-context experiment: the same
   model glossing each word with and without its sentence. The gap is the value of context.
3. **ASR quality by difficulty** — joins the team's hand-rated difficulty categories
   (`videos_dataset/`) onto ElevenLabs' shipped per-word confidence. No re-transcription,
   no ASR built: shows confidence degrades monotonically with rated difficulty.
4. **Uncertainty** — does the pipeline's per-word ASR log-prob actually predict errors?
   (ROC-AUC + a flag with measured precision/recall.) Also separates ASR vs translation blame.
5. **LLM-as-judge**, cross-family (DeepSeek, not Gemini) and **validated against the human
   labels** (Cohen's κ) before being trusted to scale.
6. **Failure taxonomy + safety** — categorized real failures and who they could harm.

The eval consumes the site's existing per-segment JSON shape — see [SCHEMA.md](SCHEMA.md) and
`scripts/validate_pipeline_output.py` so a teammate's pipeline output drops straight in.

## Layout
```
data/            scraped corpus (videos.json, segments/, corpus.json)
scripts/         fetch, sample, label-tool, analyze, LLM harness, charts, report
eval/label.html  self-contained blind labeling tool (audio + keyboard, autosaves)
out/             gold sample, labels, results.json, REPORT.md, charts
.env             OPENROUTER_API_KEY (gitignored)
```

## Run
```bash
./run_all.sh --mock     # full pipeline on synthetic labels, no key (sanity check)
./run_all.sh            # offline metrics on your real out/gold_labels.json
./run_all.sh --llm      # + live judge + context/no-context baseline (needs key)
```

Labeling: open `eval/label.html`, judge each item, **Export** → drop the file at
`out/gold_labels.json`. Blind by design (the labeler never sees the model's confidence
or which stratum an item came from).

Everything up to the human labels is seeded and regenerates deterministically.
