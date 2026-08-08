# Armenian ASR model comparison

**36 transcription runs across 33 distinct models (three models appear in two
configurations), scored against human-corrected references on the labeled TikTok
dataset.** Headline: **ElevenLabs Scribe v1 leads (WER 0.061)**,
Gemini is the only competitive LLM family (best: `gemini-3-flash-preview`, 0.104), and
the classic open-source / commodity ASR stack (Whisper, Chirp, Deepgram, Parakeet, …)
is currently unusable for Armenian — most of it scores above 0.5 WER, with failure
modes ranging from empty output to transliterating Armenian into Latin or Cyrillic.

Date: 2026-08-08. Reproduce with:

```bash
python3 scripts/asr_wer_models.py --refs <path-to>/asr_refs.json
```

## Method

- **References:** 25 audio segments sampled from the corpus, stratified by difficulty
  (`scripts/build_asr_sample.py`, seed 20260808), hand-corrected to verbatim in the
  `eval/asr.html` tool and exported as `asr_refs.json`. Segment metadata (video,
  timestamps, seed text) is embedded in `eval/asr.html`, so `out/asr_items.json` is
  not needed.
- **Hypotheses:** whole-video transcripts in `dataset/transcripts/<model>.<variant>/<category>/<video_id>.txt`
  (19 videos of `videos_dataset_labeled/`, ~20 min of audio total).
- **Scoring:** each reference is aligned to the best-matching contiguous window of the
  video transcript (infix Levenshtein — prefix/suffix outside the window is free,
  necessary because these transcripts are unsegmented). Normalization = `asr_wer.py`'s
  `norm()`: lowercase, punctuation stripped (Armenian + ASCII `:;!?`), `եւ` → `և`.
  WER aggregates word edits over reference words per category and overall.

### Caveats

- **n = 25 segments** (~700 reference words). Differences of a few points are noise;
  tiers are meaningful, close rankings within a tier are not.
- The references were produced by **correcting ElevenLabs output**, which gives the
  ElevenLabs rows a home-field advantage of unknown size (annotator anchoring,
  shared orthographic conventions).
- Infix alignment cannot penalize extra hypothesis text outside the matched window,
  so verbose/hallucinating models are scored slightly leniently.

## Results (overall WER, best → worst)

| model | n | formal | single_speaker | multi_speakers | songs | difficult | **WER** | CER |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| elevenlabs_scribe_v1.basic | 25 | 0.000 | 0.038 | 0.128 | 0.071 | 0.167 | **0.061** | 0.034 |
| elevenlabs_scribe_v2.basic | 25 | 0.021 | 0.057 | 0.154 | 0.071 | 0.167 | **0.076** | 0.038 |
| gemini_3_flash_preview.basic | 25 | 0.021 | 0.113 | 0.128 | 0.161 | 0.194 | **0.104** | 0.043 |
| gemini_2.5_flash.basic | 25 | 0.000 | 0.057 | 0.256 | 0.161 | 0.250 | **0.112** | 0.051 |
| gemini_3.1_pro_preview.basic | 25 | 0.000 | 0.151 | 0.154 | 0.196 | 0.250 | **0.122** | 0.052 |
| gemini_3.1_flash_lite.basic | 25 | 0.043 | 0.057 | 0.231 | 0.161 | 0.278 | **0.126** | 0.046 |
| gemini_2.5_flash_lite.basic | 25 | 0.032 | 0.113 | 0.205 | 0.161 | 0.361 | **0.140** | 0.072 |
| gemini_2.5_pro.basic | 25 | 0.011 | 0.170 | 0.205 | 0.161 | 0.333 | **0.140** | 0.059 |
| gemini_3.5_flash.basic | 25 | 0.043 | 0.170 | 0.154 | 0.179 | 0.278 | **0.140** | 0.058 |
| gemini_3.6_flash.basic | 25 | 0.032 | 0.208 | 0.205 | 0.268 | 0.194 | **0.158** | 0.072 |
| openai_gpt_transcribe.basic | 25 | 0.032 | 0.208 | 0.256 | 0.214 | 0.472 | **0.191** | 0.082 |
| openai_gpt_transcribe.tuned | 25 | 0.032 | 0.208 | 0.256 | 0.214 | 0.472 | **0.191** | 0.081 |
| gemini_3.5_flash_lite.basic | 25 | 0.043 | 0.358 | 0.308 | 0.196 | 0.222 | **0.194** | 0.081 |
| gpt_audio.basic | 25 | 0.043 | 0.302 | 0.462 | 0.393 | 0.472 | **0.277** | 0.131 |
| gpt_audio_mini.basic | 25 | 0.128 | 0.358 | 0.487 | 0.446 | 0.333 | **0.313** | 0.144 |
| openai_gpt_4o_mini_transcribe.basic | 25 | 0.096 | 0.358 | 0.487 | 0.804 | 0.500 | **0.396** | 0.233 |
| elevenlabs_scribe_v2_realtime.hye | 25 | 0.096 | 0.283 | 0.769 | 0.714 | 0.694 | **0.428** | 0.221 |
| voxtral_small_24b.basic | 25 | 0.160 | 0.415 | 0.667 | 0.643 | 0.778 | **0.457** | 0.214 |
| google_chirp_3.chunked | 25 | 0.096 | 0.717 | 0.333 | 0.732 | 0.889 | **0.478** | 0.366 |
| openai_gpt_4o_transcribe.basic | 25 | 0.245 | 0.434 | 0.538 | 0.893 | 0.750 | **0.518** | 0.234 |
| openai_whisper_1.basic | 25 | 0.351 | 0.717 | 0.744 | 0.446 | 0.611 | **0.529** | 0.186 |
| inkling.basic | 25 | 0.181 | 0.491 | 0.795 | 0.714 | 0.944 | **0.532** | 0.235 |
| deepgram_nova_3.basic | 25 | 0.309 | 0.642 | 0.590 | 0.768 | 0.611 | **0.543** | 0.368 |
| openai_whisper_large_v3_turbo.basic | 25 | 0.617 | 0.509 | 0.821 | 0.518 | 0.889 | **0.640** | 0.352 |
| elevenlabs_scribe_v2_realtime.basic | 25 | 0.223 | 1.000 | 0.590 | 1.000 | 1.000 | **0.680** | 0.554 |
| inkling_small.basic | 24 | 0.649 | 0.679 | 0.971 | 0.804 | 0.944 | **0.766** | 0.545 |
| qwen_qwen3_asr_flash_2026_02_10.basic | 25 | 0.596 | 0.849 | 0.974 | 0.821 | 1.000 | **0.795** | 0.436 |
| openai_whisper_large_v3.basic | 25 | 0.883 | 0.887 | 0.897 | 0.839 | 0.667 | **0.849** | 0.603 |
| mimo_v2.5.basic | 25 | 0.915 | 0.868 | 0.923 | 0.911 | 0.861 | **0.899** | 0.707 |
| google_chirp_3.basic | 25 | 0.957 | 0.717 | 0.974 | 1.000 | 1.000 | **0.928** | 0.921 |
| nvidia_parakeet_tdt_0.6b_v3.basic | 25 | 0.989 | 0.906 | 1.000 | 1.000 | 1.000 | **0.978** | 0.982 |
| microsoft_mai_transcribe_1.5.basic | 25 | 0.989 | 0.925 | 1.000 | 1.000 | 1.000 | **0.982** | 0.980 |
| mistralai_voxtral_mini_transcribe.basic | 25 | 1.000 | 0.906 | 1.000 | 1.000 | 1.000 | **0.982** | 0.981 |
| x_ai_grok_stt_1.0.basic | 25 | 0.989 | 1.000 | 1.000 | 1.000 | 1.000 | **0.996** | 0.992 |
| fish_audio_transcribe_1.basic | 25 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | **1.000** | 1.000 |
| nemotron_3_nano_omni_free.basic | 25 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | **1.000** | 0.999 |

## Key findings

1. **ElevenLabs Scribe wins, and v1 ≥ v2** (0.061 vs 0.076; the gap is ~5 word-edits,
   i.e. within noise — but the newer version buys nothing here).
2. **Gemini is the only viable LLM alternative** (~$0.01/audio-minute via OpenRouter).
   Release order inverts quality: `3-flash-preview` (0.104) and `2.5-flash` (0.112) beat
   every newer flash; `3.5/3.6-flash` land at the bottom of the family.
3. **OpenAI**: dedicated `gpt-transcribe` (0.191) clearly beats the chat `gpt-audio`
   models; mini variants beat their bigger siblings on Armenian.
4. **Realtime ASR degrades hard.** Scribe v2 realtime needs `language_code=hye` pinned
   (auto-detect emits Cyrillic/Latin transliterations → 0.680); even pinned it drops
   entire stretches of hard audio (0.428). Only defensible for live-captioning formal speech.
5. **The commodity ASR stack fails on Armenian**: Whisper large v3 (0.849) produces
   misspelled Armenian and loses to 2022-era `whisper-1` (0.529); Chirp 3 returns
   empty output for most videos unless audio is chunked (0.928 → 0.478); Grok STT and
   Parakeet emit phonetic Latin transliteration; fish-audio emits Perso-Arabic script;
   Nemotron free outputs a literal "(No output)".

## Provenance of `dataset/transcripts/` folders

| folder pattern | produced by | notes |
|---|---|---|
| `elevenlabs_scribe_v{1,2}.basic` | `speech_recognition/video_transcribe.py -m scribe_v{1,2}` | batch API, language auto-detect; JSON sidecars carry per-word logprobs/timings |
| `elevenlabs_scribe_v2_realtime.{basic,hye}` | `speech_recognition/video_transcribe_realtime.py` | WebSocket streaming, VAD commits; `.hye` pins `-l hye` |
| `gemini_*.basic`, `gpt_audio*`, `inkling*`, `mimo*`, `voxtral_small*`, `nemotron*` | `speech_recognition/video_transcribe_gemini.py -m <model> -l Armenian` (OpenRouter chat-completions) | FLAC 16 kHz mono, except WAV for `gpt_audio*`/`inkling_small` (models reject FLAC); `top_p=1` |
| `openai_*`, `google_chirp_3.*`, `deepgram_*`, `qwen_*`, `x_ai_*`, `fish_*`, `microsoft_*`, `nvidia_parakeet_*`, `mistralai_voxtral_mini_*` | external runs via the providers' dedicated transcription APIs | `google_chirp_3.chunked` = same model, audio pre-chunked (rescues most empty outputs) |

Known blemishes: `inkling_small.basic` has 18/19 videos (one persistent provider-side
error); `nemotron_3_nano_omni_free.basic` transcripts are literal "(No output)"
placeholders; `openai_gpt_transcribe.tuned` is byte-identical to `.basic` for 17/19
videos, so this reference set cannot measure the tuning's effect; `muse_spark_1.1/1.2`
are absent — the models sit behind an OpenRouter 18+ account confirmation.

Costs (OpenRouter runs, whole 19-video set): Gemini $0.03–$2.37 per model
(reasoning tokens dominate; `3.1-pro-preview` is the expensive outlier),
`gpt_audio` $0.92, everything else ≤ $0.35.
