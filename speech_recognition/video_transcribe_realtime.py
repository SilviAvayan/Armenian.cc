#!/usr/bin/env python3
"""
video_transcribe_realtime.py
============================

Produce a transcript of the spoken speech in a video file using ElevenLabs'
realtime (streaming WebSocket) speech-to-text, e.g. the scribe_v2_realtime
model. The batch API (see video_transcribe.py) does not serve realtime models,
and vice versa.

Pipeline:
    video --(ffmpeg)--> PCM16 mono 16 kHz --(WebSocket stream)--> committed text

The audio is streamed in small chunks; the server's VAD commits finished
segments as it goes and a final manual commit flushes the tail. The committed
segments are concatenated into the transcript.

Usage:
    export ELEVENLABS_API_KEY="sk_..."
    python video_transcribe_realtime.py input.mp4
    python video_transcribe_realtime.py input.mp4 -o out.txt -j out.json
    python video_transcribe_realtime.py input.mp4 -l hye --speedup 1

Notes:
    - Without -l/--language the model auto-detects the language per segment,
      which in practice is unstable (it may emit transliterations in the wrong
      script). Pin the language when it is known.
    - --speedup streams faster than realtime. 4x worked identically to 1x in
      our tests, but 1 is the safest choice if results look truncated.

Requirements:
    - Python 3.9+, ffmpeg on PATH
    - pip install elevenlabs
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from elevenlabs.client import AsyncElevenLabs
    from elevenlabs import RealtimeEvents
    from elevenlabs.realtime.scribe import AudioFormat, CommitStrategy
except ImportError:
    sys.exit("Missing dependency. Install it with:  pip install elevenlabs")

SAMPLE_RATE = 16_000
CHUNK_SECS = 0.5
CHUNK_BYTES = int(SAMPLE_RATE * 2 * CHUNK_SECS)  # 16-bit mono
DEFAULT_MODEL = "scribe_v2_realtime"

ERROR_EVENTS = (
    RealtimeEvents.ERROR, RealtimeEvents.AUTH_ERROR, RealtimeEvents.TRANSCRIBER_ERROR,
    RealtimeEvents.QUOTA_EXCEEDED, RealtimeEvents.RATE_LIMITED, RealtimeEvents.INPUT_ERROR,
    RealtimeEvents.QUEUE_OVERFLOW, RealtimeEvents.RESOURCE_EXHAUSTED,
    RealtimeEvents.SESSION_TIME_LIMIT_EXCEEDED, RealtimeEvents.CHUNK_SIZE_EXCEEDED,
)


def log(msg: str, quiet: bool) -> None:
    if not quiet:
        print(msg, file=sys.stderr)


def extract_pcm(video: Path) -> bytes:
    if shutil.which("ffmpeg") is None:
        sys.exit("ffmpeg not found on PATH. Install it from https://ffmpeg.org/download.html")
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(video), "-vn", "-ac", "1",
         "-ar", str(SAMPLE_RATE), "-f", "s16le", "-"],
        capture_output=True)
    if proc.returncode != 0:
        sys.exit(f"ffmpeg failed while extracting audio:\n{proc.stderr.decode().strip()}")
    if not proc.stdout:
        sys.exit("No audio was extracted. Does the video actually contain an audio track?")
    return proc.stdout


async def stream_transcribe(pcm: bytes, *, model: str, language: str | None,
                            speedup: float, quiet: bool) -> tuple[str, list[dict]]:
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        sys.exit("Set your API key first:  export ELEVENLABS_API_KEY=sk_...")
    client = AsyncElevenLabs(api_key=api_key)

    committed: list[str] = []
    events: list[dict] = []

    options = {
        "model_id": model,
        "audio_format": AudioFormat.PCM_16000,
        "sample_rate": SAMPLE_RATE,
        "commit_strategy": CommitStrategy.VAD,
    }
    if language:
        options["language_code"] = language
    conn = await client.speech_to_text.realtime.connect(options)

    def on_committed(data):
        events.append(data)
        text = (data.get("text") or "").strip()
        if text:
            committed.append(text)

    def on_error(data):
        events.append(data)
        log(f"error event: {data}", quiet)

    conn.on(RealtimeEvents.COMMITTED_TRANSCRIPT, on_committed)
    for ev in ERROR_EVENTS:
        conn.on(ev, on_error)

    n_chunks = (len(pcm) + CHUNK_BYTES - 1) // CHUNK_BYTES
    log(f"Streaming {len(pcm) / (SAMPLE_RATE * 2):.1f}s of audio "
        f"in {n_chunks} chunk(s) at {speedup:g}x realtime ...", quiet)
    for i in range(0, len(pcm), CHUNK_BYTES):
        await conn.send({"audio_base_64": base64.b64encode(pcm[i:i + CHUNK_BYTES]).decode()})
        await asyncio.sleep(CHUNK_SECS / speedup)

    # half a second of silence lets VAD close the last speech segment,
    # then a manual commit flushes whatever is still buffered
    await conn.send({"audio_base_64": base64.b64encode(b"\x00" * CHUNK_BYTES).decode()})
    await asyncio.sleep(1.0)
    try:
        await conn.commit()
    except Exception as e:  # noqa: BLE001
        log(f"final commit failed: {e}", quiet)
    await asyncio.sleep(3.0)
    await conn.close()

    return " ".join(committed).strip(), events


def main() -> None:
    p = argparse.ArgumentParser(
        description="Speech transcription from a video file via ElevenLabs realtime STT.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("video", type=Path, help="Path to the input video file")
    p.add_argument("-o", "--output", type=Path, help="Write transcript to this file (default: stdout)")
    p.add_argument("-j", "--json", type=Path, metavar="PATH",
                   help="Also write a JSON sidecar with the raw committed/error events")
    p.add_argument("-l", "--language", default=None,
                   help="ISO-639-1/3 language code, e.g. hye, eng. Omit for auto-detect "
                        "(unstable in practice — pin it when known).")
    p.add_argument("-m", "--model", default=DEFAULT_MODEL,
                   help=f"Realtime model id (default: {DEFAULT_MODEL})")
    p.add_argument("--speedup", type=float, default=4.0,
                   help="Stream at N x realtime (default: 4; use 1 if output looks truncated)")
    p.add_argument("-q", "--quiet", action="store_true", help="Suppress progress messages")
    args = p.parse_args()

    if not args.video.is_file():
        sys.exit(f"Input file not found: {args.video}")

    pcm = extract_pcm(args.video)
    transcript, events = asyncio.run(stream_transcribe(
        pcm, model=args.model, language=args.language,
        speedup=args.speedup, quiet=args.quiet))

    if args.json:
        args.json.write_text(json.dumps(
            {"source": args.video.name, "model_id": args.model,
             "requested_language": args.language, "text": transcript, "events": events},
            ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        log(f"Event data written to {args.json}", args.quiet)

    if args.output:
        args.output.write_text(transcript + "\n", encoding="utf-8")
        log(f"Transcript written to {args.output}", args.quiet)
    else:
        print(transcript)


if __name__ == "__main__":
    main()
