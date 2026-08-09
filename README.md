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

## Layout**Not in the repo** (gitignored or external, expected locally):
`data/` scraped corpus — re-fetch with `scripts/fetch_corpus.py`;
`out/*` analysis artifacts — regenerate with `./run_all.sh`;
`out/gold_labels.json` and `out/asr_refs.json` — exported from the `eval/` tools;
`videos_dataset/` source audio — external folder, path set by `$VIDEOS_DATASET`
(defaults to a hardcoded local path in `scripts/difficulty.py`); steps that need it
skip cleanly when it's absent.

## Run
```bash
./run_all.sh --mock     # full pipeline on synthetic labels, no key (sanity check)
./run_all.sh            # offline metrics on your real out/gold_labels.json
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
- Metrics quoted in `PITCH_BRIEF.md` come from `out/REPORT.md` and `out/*.json`, which
  are gitignored. They do not regenerate from a fresh clone without labels.

## License
Apache License 2.0 — see [LICENSE.md](LICENSE.md).
