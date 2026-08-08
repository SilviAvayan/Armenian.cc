# ASR model quality (ground-truth-free)

Benchmark: 19 clips. No human references were used, so these are NOT
accuracy numbers. `vs-scribe` is the median per-clip word-distance to
`elevenlabs_scribe_v2.basic` (production baseline, itself imperfect --
its committed `difficult/www.ishkhanutyun` transcript is a repetition loop).
For real WER: label `eval/asr.html` -> `out/asr_refs.json` ->
`scripts/asr_wer_models.py`.

| model | n | coverage | empty | loops | armenian % | vs-scribe (median) |
|---|---|---|---|---|---|---|
| gemini_2.5_flash.basic | 19 | 1.00 | 0.00 | 0.05 | 99.5 | 0.173 |
| gemini_2.5_pro.basic | 19 | 1.00 | 0.00 | 0.05 | 99.7 | 0.186 |
| gemini_3.1_pro_preview.basic | 19 | 1.00 | 0.00 | 0.05 | 99.7 | 0.227 |
| gemini_3.5_flash.basic | 19 | 1.00 | 0.00 | 0.05 | 99.8 | 0.231 |
| gemini_3_flash_preview.basic | 19 | 1.00 | 0.00 | 0.05 | 99.4 | 0.234 |
| gemini_3.1_flash_lite.basic | 19 | 1.00 | 0.00 | 0.10 | 99.4 | 0.236 |
| gemini_3.6_flash.basic | 19 | 1.00 | 0.00 | 0.05 | 99.6 | 0.238 |
| gemini_2.5_flash_lite.basic | 19 | 1.00 | 0.00 | 0.10 | 99.6 | 0.243 |
| gemini_3.5_flash_lite.basic | 19 | 1.00 | 0.00 | 0.05 | 98.7 | 0.323 |
| gpt_audio.basic | 19 | 1.00 | 0.00 | 0.05 | 99.7 | 0.412 |
| gpt_audio_mini.basic | 19 | 1.00 | 0.00 | 0.10 | 99.5 | 0.42 |
| openai_gpt_4o_mini_transcribe.basic | 19 | 1.00 | 0.00 | 0.05 | 89.1 | 0.425 |
| openai_gpt_4o_transcribe.basic | 19 | 1.00 | 0.00 | 0.10 | 94.0 | 0.624 |
| voxtral_small_24b.basic | 19 | 1.00 | 0.00 | 0.21 | 99.5 | 0.644 |
| openai_whisper_1.basic | 19 | 1.00 | 0.00 | 0.00 | 99.8 | 0.75 |
| openai_whisper_large_v3_turbo.basic | 19 | 1.00 | 0.00 | 0.00 | 92.3 | 0.805 |
| openai_whisper_large_v3.basic | 19 | 1.00 | 0.00 | 0.00 | 99.8 | 0.871 |
| inkling_small.basic | 18 | 1.00 | 0.00 | 0.28 | 99.9 | 0.903 |
| microsoft_mai_transcribe_1.5.basic | 19 | 1.00 | 0.00 | 0.05 | 0.0 | 1.0 |
| nemotron_3_nano_omni_free.basic | 19 | 1.00 | 0.00 | 0.00 | 0.0 | 1.0 |
| qwen_qwen3_asr_flash_2026_02_10.basic | 19 | 1.00 | 0.00 | 0.16 | 47.4 | 1.0 |
| fish_audio_transcribe_1.basic | 19 | 1.00 | 0.00 | 0.21 | 0.0 | 1.036 |
| elevenlabs_scribe_v2.basic | 19 | 1.00 | 0.00 | 0.05 | 99.3 | - |
| openai_gpt_transcribe.basic | 19 | 0.95 | 0.05 | 0.00 | 99.4 | 0.33 |
| deepgram_nova_3.basic | 19 | 0.95 | 0.05 | 0.00 | 99.7 | 0.644 |
| inkling.basic | 19 | 0.95 | 0.05 | 0.16 | 99.9 | 0.8 |
| mistralai_voxtral_mini_transcribe.basic | 19 | 0.90 | 0.10 | 0.10 | 0.0 | 1.0 |
| nvidia_parakeet_tdt_0.6b_v3.basic | 19 | 0.90 | 0.10 | 0.00 | 0.0 | 1.0 |
| x_ai_grok_stt_1.0.basic | 19 | 0.84 | 0.16 | 0.05 | 0.0 | 1.0 |
| mimo_v2.5.basic | 19 | 0.84 | 0.16 | 0.16 | 76.9 | 1.327 |
| google_chirp_3.chunked | 19 | 0.63 | 0.37 | 0.00 | 99.2 | 0.472 |
| google_chirp_3.basic | 19 | 0.21 | 0.79 | 0.00 | 74.7 | 0.647 |

`loops` counts committed transcripts that are decoder repetition
loops, not transcriptions. `armenian %` near 0 means the model wrote
the wrong script entirely (Latin / Arabic / Devanagari).
