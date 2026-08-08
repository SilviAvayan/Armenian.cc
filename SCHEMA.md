# Pipeline output schema (what the eval consumes)

The eval runs on **per-video segment files** in exactly the shape armenian.cc already
produces. If the team's pipeline (ElevenLabs → Gemini) emits this, every metric —
accuracy, uncertainty, failure taxonomy, difficulty breakdown — runs with no adapter.

## Per-video segments: `list[Segment]`

```jsonc
[
  {
    "start": 0.0,                 // float, seconds — segment start in the video
    "end": 5.119,                 // float, seconds — segment end
    "text": "Սոխը մանր կտրում ենք։", // str — ElevenLabs transcript for this segment (REQUIRED)
    "words": [                    // list — one entry per token (REQUIRED, >=1)
      {
        "text": "Սոխը",           // str — Armenian surface token (REQUIRED)
        "start": 0.399,           // float — word start (optional but enables audio sync)
        "end": 0.68,              // float — word end (optional)
        "translation": "лук",     // str — Russian gloss IN CONTEXT (REQUIRED for gloss eval)
        "logprob": -0.24          // float <= 0 — ASR confidence (REQUIRED for uncertainty eval)
      }
    ],
    "explanation": "Лук мелко режем.", // str — full-phrase RU translation (REQUIRED for phrase eval)
    "notes": [                    // list — model's linguistic notes (optional; enables notes eval)
      { "word": "ենք", "gloss": "делаем", "note": "вспом. глагол, наст. вр., 1 л. мн." }
    ]
  }
]
```

## Video index entry (one per video), used to locate audio + difficulty

```jsonc
{
  "id": "handle_1234567890",          // str — MUST equal the mp4 basename (handle_videoid)
  "handle": "nikol.pashinyan_pm",     // str
  "url": "https://www.tiktok.com/@handle/video/1234567890",
  "src": "https://videos.armenian.cc/video_handle_1234567890.mp4"  // playable audio/video URL
}
```

## Rules the validator enforces
- `text`, `words`, `explanation` present on every segment; `words` non-empty.
- each word has `text`; `translation` and `logprob` present for ≥90% of words.
- `logprob` is a number ≤ 0 (natural-log probability).
- `id` matches `^[A-Za-z0-9._]+_\d+$` and equals the mp4 filename stem, so difficulty
  categories in `videos_dataset/` join correctly.

Run: `python3 scripts/validate_pipeline_output.py path/to/segments.json`
