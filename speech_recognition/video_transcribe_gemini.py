#!/usr/bin/env python3
"""
video_transcribe_gemini.py
==========================

Produce a transcript of the spoken speech in a video file, using a Gemini
model through the OpenRouter chat-completions API.

Pipeline:
    video  --(ffmpeg)-->  mono 16 kHz FLAC audio  --(OpenRouter / Gemini)-->  text

Usage:
    export OPENROUTER_API_KEY="sk-or-..."
    python video_transcribe_gemini.py input.mp4
    python video_transcribe_gemini.py input.mp4 -o transcript.txt
    python video_transcribe_gemini.py input.mp4 -o transcript.txt --json transcript.json
    python video_transcribe_gemini.py lecture.mkv --language Armenian
    python video_transcribe_gemini.py long_podcast.mp4 --max-chunk-minutes 10

The audio is sent base64-encoded inside a chat-completions request with the
"input_audio" content type. Long videos are split into chunks (cut at silence,
so words are never sliced in half) because the whole audio must fit into a
single request; see --max-chunk-minutes.

The --json sidecar stores per-chunk raw model output, offsets and token usage.
Unlike a dedicated ASR API, Gemini returns free-form text, so there are no
word-level timestamps or confidences.

Requirements:
    - Python 3.9+
    - ffmpeg and ffprobe on PATH   (https://ffmpeg.org/download.html)
    - pip install requests
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("Missing dependency. Install it with:  pip install requests")


# --- Audio extraction settings ------------------------------------------------
# Mono 16 kHz is the standard input for speech recognition and keeps uploads
# tiny compared to the source video. FLAC is lossless, so no accuracy is lost
# to compression, and Gemini accepts it natively. Some models only take WAV or
# MP3 (e.g. OpenAI's gpt-audio family) — pick with --audio-format.
SAMPLE_RATE = 16_000
AUDIO_FORMATS = {"flac": "flac", "wav": "pcm_s16le", "mp3": "libmp3lame"}
AUDIO_EXT = "flac"                      # overridden by --audio-format
AUDIO_CODEC = AUDIO_FORMATS[AUDIO_EXT]

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "google/gemini-2.5-flash"
# The full audio must fit into one request as base64 (~+33% size), so long
# recordings have to be split. 15 min of mono 16 kHz FLAC speech is roughly
# 5-8 MB, comfortably under OpenRouter's request size limits.
DEFAULT_MAX_CHUNK_MINUTES = 15.0
REQUEST_TIMEOUT = 600  # seconds; transcribing a long chunk can take a while
MAX_RETRIES = 3

BASE_PROMPT = (
    "Transcribe the speech in this audio verbatim. "
    "Output only the transcript text, with punctuation, and nothing else - "
    "no introduction, no commentary, no markdown formatting. "
    "If there is no speech in the audio, output nothing."
)


def log(msg: str, quiet: bool) -> None:
    if not quiet:
        print(msg, file=sys.stderr)


def require_ffmpeg() -> None:
    missing = [t for t in ("ffmpeg", "ffprobe") if shutil.which(t) is None]
    if missing:
        sys.exit(
            f"Required tool(s) not found on PATH: {', '.join(missing)}.\n"
            "Install ffmpeg from https://ffmpeg.org/download.html"
        )


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    """Run a command, raising CalledProcessError with captured output on failure."""
    return subprocess.run(cmd, check=True, capture_output=True, text=True)


def extract_audio(video: Path, out: Path, quiet: bool) -> None:
    log(f"Extracting audio from {video.name} ...", quiet)
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video),
        "-vn",                       # drop the video stream
        "-ac", "1",                  # mono
        "-ar", str(SAMPLE_RATE),     # 16 kHz
        "-c:a", AUDIO_CODEC,
        str(out),
    ]
    try:
        _run(cmd)
    except subprocess.CalledProcessError as e:
        sys.exit(f"ffmpeg failed while extracting audio:\n{e.stderr.strip()}")
    if not out.exists() or out.stat().st_size == 0:
        sys.exit("No audio was extracted. Does the video actually contain an audio track?")


def probe_duration(path: Path) -> float:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    try:
        return float(_run(cmd).stdout.strip())
    except (subprocess.CalledProcessError, ValueError):
        return 0.0


def detect_silence_midpoints(path: Path, noise_db: float = -30.0, min_silence: float = 0.4) -> list[float]:
    """Use ffmpeg's silencedetect filter to find the midpoint of each silent gap."""
    cmd = [
        "ffmpeg", "-i", str(path),
        "-af", f"silencedetect=noise={noise_db}dB:d={min_silence}",
        "-f", "null", "-",
    ]
    # silencedetect writes to stderr; ffmpeg exits 0 for this null-muxer run.
    proc = subprocess.run(cmd, capture_output=True, text=True)
    starts = [float(x) for x in re.findall(r"silence_start:\s*([\d.]+)", proc.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end:\s*([\d.]+)", proc.stderr)]
    return [(s + e) / 2.0 for s, e in zip(starts, ends)]


def choose_cut_points(duration: float, silence_mids: list[float], max_chunk: float) -> list[float]:
    """
    Greedily choose timestamps at which to split the audio so that no chunk is
    longer than `max_chunk` seconds, preferring to cut inside a silence so words
    are never sliced in half. Falls back to a hard cut only when a window
    contains no detected silence.
    """
    mids = sorted(silence_mids)
    cuts: list[float] = []
    last = 0.0
    while duration - last > max_chunk:
        window_end = last + max_chunk
        candidate = None
        for m in mids:
            if m <= last:
                continue
            if m <= window_end:
                candidate = m          # keep the latest silence inside the window
            else:
                break
        if candidate is None:
            candidate = window_end     # no silence found; hard cut
        cuts.append(round(candidate, 3))
        last = candidate
    return cuts


def split_audio(path: Path, cuts: list[float], tmpdir: Path, quiet: bool) -> list[Path]:
    bounds: list = [0.0, *cuts, None]
    segments: list[Path] = []
    log(f"Splitting audio into {len(bounds) - 1} chunk(s) ...", quiet)
    for i in range(len(bounds) - 1):
        start, end = bounds[i], bounds[i + 1]
        seg = tmpdir / f"chunk_{i:03d}.{AUDIO_EXT}"
        cmd = ["ffmpeg", "-y", "-i", str(path), "-ss", f"{start}"]
        if end is not None:
            cmd += ["-to", f"{end}"]
        cmd += ["-ac", "1", "-ar", str(SAMPLE_RATE), "-c:a", AUDIO_CODEC, str(seg)]
        try:
            _run(cmd)
        except subprocess.CalledProcessError as e:
            sys.exit(f"ffmpeg failed while splitting audio:\n{e.stderr.strip()}")
        segments.append(seg)
    return segments


def build_prompt(language: str | None) -> str:
    if language:
        return f"{BASE_PROMPT} The audio is in {language}; transcribe it in that language."
    return BASE_PROMPT


def transcribe_chunk(api_key: str, audio_path: Path, *, model: str, prompt: str,
                     temperature: float) -> dict:
    """
    Send one audio chunk to OpenRouter and return the raw response JSON.
    Retries with exponential backoff on rate limits and transient server errors.
    """
    audio_b64 = base64.b64encode(audio_path.read_bytes()).decode("ascii")
    payload = {
        "model": model,
        "temperature": temperature,
        "top_p": 1,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "input_audio",
                 "input_audio": {"data": audio_b64, "format": AUDIO_EXT}},
            ],
        }],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    last_error = ""
    attempt = 0
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(OPENROUTER_URL, headers=headers, json=payload,
                                 timeout=REQUEST_TIMEOUT)
        except requests.RequestException as e:
            last_error = str(e)
        else:
            if resp.status_code == 200:
                return resp.json()
            last_error = f"HTTP {resp.status_code}: {resp.text[:500]}"
            # Only retry what can plausibly succeed on a second try.
            if resp.status_code not in (408, 429, 500, 502, 503, 504):
                break
        if attempt < MAX_RETRIES:
            time.sleep(2 ** attempt)
    raise RuntimeError(f"OpenRouter request failed after {attempt} attempt(s): {last_error}")


def response_text(response: dict) -> str:
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise RuntimeError(f"Unexpected OpenRouter response shape: {json.dumps(response)[:500]}")
    # Some providers return content as a list of typed parts instead of a string.
    if isinstance(content, list):
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return (content or "").strip()


def transcribe_video(video: Path, *, model: str, language: str | None, temperature: float,
                     max_chunk_minutes: float, keep_audio: bool, quiet: bool) -> tuple[str, dict]:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        sys.exit("Set your API key first:  export OPENROUTER_API_KEY=sk-or-...")

    prompt = build_prompt(language)

    tmpdir = Path(tempfile.mkdtemp(prefix="vtg_"))
    try:
        audio = tmpdir / f"audio.{AUDIO_EXT}"
        extract_audio(video, audio, quiet)

        max_chunk = max_chunk_minutes * 60.0
        duration = probe_duration(audio)
        if max_chunk > 0 and duration > max_chunk:
            mids = detect_silence_midpoints(audio)
            cuts = choose_cut_points(duration, mids, max_chunk)
            chunks = split_audio(audio, cuts, tmpdir, quiet)
            offsets = [0.0, *cuts]
        else:
            chunks = [audio]
            offsets = [0.0]

        texts: list[str] = []
        chunk_meta: list[dict] = []
        for idx, (chunk, offset) in enumerate(zip(chunks, offsets), 1):
            log(f"Transcribing chunk {idx}/{len(chunks)} ...", quiet)
            try:
                response = transcribe_chunk(
                    api_key, chunk, model=model, prompt=prompt, temperature=temperature,
                )
            except RuntimeError as e:
                sys.exit(f"Transcription failed on chunk {idx}: {e}")
            piece = response_text(response)
            texts.append(piece)
            chunk_meta.append({
                "index": idx,
                "offset": offset,
                "text": piece,
                "finish_reason": response.get("choices", [{}])[0].get("finish_reason"),
                "usage": response.get("usage"),
                "provider_model": response.get("model"),
            })

        transcript = " ".join(t for t in texts if t).strip()
        data = {
            "source": video.name,
            "model": model,
            "requested_language": language,
            "prompt": prompt,
            "duration_seconds": round(duration, 3),
            "text": transcript,
            "chunks": chunk_meta,
        }
        return transcript, data
    finally:
        if keep_audio:
            log(f"Extracted audio kept in: {tmpdir}", quiet)
        else:
            shutil.rmtree(tmpdir, ignore_errors=True)


def main() -> None:
    p = argparse.ArgumentParser(
        description="Speech transcription from a video file via Gemini through OpenRouter.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("video", type=Path, help="Path to the input video file")
    p.add_argument("-o", "--output", type=Path, help="Write transcript to this file (default: stdout)")
    p.add_argument("-j", "--json", type=Path, metavar="PATH",
                   help="Also write a JSON sidecar with per-chunk raw output, offsets and token usage")
    p.add_argument("-l", "--language", default=None,
                   help="Spoken language as a plain name (e.g. Armenian, English, Russian) - "
                        "used as a hint in the prompt. Omit for auto-detect.")
    p.add_argument("-m", "--model", default=DEFAULT_MODEL,
                   help=f"OpenRouter model id (default: {DEFAULT_MODEL})")
    p.add_argument("-t", "--temperature", type=float, default=0.0,
                   help="Sampling temperature; 0 is the most deterministic (default: 0)")
    p.add_argument("-f", "--audio-format", choices=sorted(AUDIO_FORMATS), default="flac",
                   help="Audio format sent to the model (default: flac; some models "
                        "only accept wav or mp3)")
    p.add_argument("--max-chunk-minutes", type=float, default=DEFAULT_MAX_CHUNK_MINUTES,
                   help="Split long audio into <=N-minute chunks, cut at silence. "
                        f"0 = never split (default: {DEFAULT_MAX_CHUNK_MINUTES:g})")
    p.add_argument("--keep-audio", action="store_true", help="Keep the extracted temp audio for debugging")
    p.add_argument("-q", "--quiet", action="store_true", help="Suppress progress messages")
    args = p.parse_args()

    if not args.video.is_file():
        sys.exit(f"Input file not found: {args.video}")

    require_ffmpeg()

    global AUDIO_EXT, AUDIO_CODEC
    AUDIO_EXT = args.audio_format
    AUDIO_CODEC = AUDIO_FORMATS[AUDIO_EXT]

    transcript, data = transcribe_video(
        args.video,
        model=args.model,
        language=args.language,
        temperature=args.temperature,
        max_chunk_minutes=args.max_chunk_minutes,
        keep_audio=args.keep_audio,
        quiet=args.quiet,
    )

    if args.json:
        args.json.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        log(f"Chunk-level data written to {args.json}", args.quiet)

    if args.output:
        args.output.write_text(transcript + "\n", encoding="utf-8")
        log(f"Transcript written to {args.output}", args.quiet)
    else:
        print(transcript)


if __name__ == "__main__":
    main()
