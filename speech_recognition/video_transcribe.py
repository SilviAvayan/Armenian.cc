#!/usr/bin/env python3
"""
video_transcribe.py
===================

Produce a verbatim transcript of the spoken speech in a video file, using
ElevenLabs' Scribe speech-to-text model.

Pipeline:
    video  --(ffmpeg)-->  mono 16 kHz FLAC audio  --(ElevenLabs Scribe)-->  text

Usage:
    export ELEVENLABS_API_KEY="sk_..."
    python video_transcribe.py input.mp4
    python video_transcribe.py input.mp4 -o transcript.txt
    python video_transcribe.py lecture.mkv --language eng --diarize
    python video_transcribe.py long_podcast.mp4 --max-chunk-minutes 20

Requirements:
    - Python 3.9+
    - ffmpeg and ffprobe on PATH   (https://ffmpeg.org/download.html)
    - pip install elevenlabs

A note on "verbatim":
    Scribe is a highly accurate ASR model, but automatic transcription is not
    the same as stenographic verbatim. It returns punctuated, paragraph-
    structured text and there is no toggle for raw, unpunctuated word soup.
    Filler words and false starts are usually captured but not guaranteed.
    Non-speech audio-event tags (laughter, applause, ...) are OFF by default so
    the output contains spoken words only; enable them with --tag-audio-events.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from elevenlabs.client import ElevenLabs
except ImportError:
    sys.exit("Missing dependency. Install it with:  pip install elevenlabs")


# --- Audio extraction settings ------------------------------------------------
# Mono 16 kHz is the standard input for speech recognition and keeps uploads
# tiny compared to the source video. FLAC is lossless, so no accuracy is lost
# to compression. Change these if you prefer WAV ("pcm_s16le"/"wav") or MP3.
SAMPLE_RATE = 16_000
AUDIO_CODEC = "flac"
AUDIO_EXT = "flac"
DEFAULT_MODEL = "scribe_v2"


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


def transcribe_file(client: "ElevenLabs", path: Path, *, model: str, language,
                    tag_events: bool, diarize: bool):
    with open(path, "rb") as fh:
        return client.speech_to_text.convert(
            file=fh,
            model_id=model,
            language_code=language,      # None => automatic language detection
            tag_audio_events=tag_events,
            diarize=diarize,
        )


def format_diarized(result) -> str:
    """
    Best-effort speaker-labelled transcript built from Scribe's word-level data.
    Falls back to plain text if word data is unavailable.
    """
    words = getattr(result, "words", None)
    if not words:
        return getattr(result, "text", "") or ""

    segments: list = []  # list of [speaker_id, text]
    for w in words:
        text = getattr(w, "text", "")
        wtype = getattr(w, "type", "word")
        spk = (getattr(w, "speaker_id", None) or "speaker_0") if wtype == "word" else None
        if spk is not None and (not segments or segments[-1][0] != spk):
            segments.append([spk, ""])
        if segments:
            segments[-1][1] += text

    def nice(spk) -> str:
        m = re.match(r"speaker_(\d+)$", str(spk))
        return f"Speaker {int(m.group(1)) + 1}" if m else str(spk)

    return "\n".join(f"{nice(s)}: {t.strip()}" for s, t in segments if t.strip())


def transcribe_video(video: Path, *, model, language, tag_events: bool, diarize: bool,
                     max_chunk_minutes: float, keep_audio: bool, quiet: bool) -> str:
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        sys.exit("Set your API key first:  export ELEVENLABS_API_KEY=sk_...")
    client = ElevenLabs(api_key=api_key)

    tmpdir = Path(tempfile.mkdtemp(prefix="vt_"))
    try:
        audio = tmpdir / f"audio.{AUDIO_EXT}"
        extract_audio(video, audio, quiet)

        max_chunk = max_chunk_minutes * 60.0
        duration = probe_duration(audio)
        if max_chunk > 0 and duration > max_chunk:
            mids = detect_silence_midpoints(audio)
            cuts = choose_cut_points(duration, mids, max_chunk)
            chunks = split_audio(audio, cuts, tmpdir, quiet)
        else:
            chunks = [audio]

        texts: list[str] = []
        for idx, chunk in enumerate(chunks, 1):
            log(f"Transcribing chunk {idx}/{len(chunks)} ...", quiet)
            try:
                result = transcribe_file(
                    client, chunk, model=model, language=language,
                    tag_events=tag_events, diarize=diarize,
                )
            except Exception as e:  # noqa: BLE001 - surface any SDK/HTTP error clearly
                sys.exit(f"ElevenLabs transcription failed on chunk {idx}: {e}")
            piece = format_diarized(result) if diarize else (getattr(result, "text", "") or "")
            texts.append(piece.strip())

        joiner = "\n\n" if diarize else " "
        return joiner.join(t for t in texts if t).strip()
    finally:
        if keep_audio:
            log(f"Extracted audio kept in: {tmpdir}", quiet)
        else:
            shutil.rmtree(tmpdir, ignore_errors=True)


def main() -> None:
    p = argparse.ArgumentParser(
        description="Verbatim speech transcription from a video file via ElevenLabs Scribe.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("video", type=Path, help="Path to the input video file")
    p.add_argument("-o", "--output", type=Path, help="Write transcript to this file (default: stdout)")
    p.add_argument("-l", "--language", default=None,
                   help="ISO-639-3 language code, e.g. eng, hye, rus. Omit for auto-detect.")
    p.add_argument("-m", "--model", default=DEFAULT_MODEL, help=f"Scribe model id (default: {DEFAULT_MODEL})")
    p.add_argument("--diarize", action="store_true", help="Label speakers (Speaker 1, Speaker 2, ...)")
    p.add_argument("--tag-audio-events", action="store_true",
                   help="Include non-speech events like (laughter), (applause)")
    p.add_argument("--max-chunk-minutes", type=float, default=0.0,
                   help="Split long audio into <=N-minute chunks, cut at silence. 0 = never split.")
    p.add_argument("--keep-audio", action="store_true", help="Keep the extracted temp audio for debugging")
    p.add_argument("-q", "--quiet", action="store_true", help="Suppress progress messages")
    args = p.parse_args()

    if not args.video.is_file():
        sys.exit(f"Input file not found: {args.video}")

    require_ffmpeg()

    transcript = transcribe_video(
        args.video,
        model=args.model,
        language=args.language,
        tag_events=args.tag_audio_events,
        diarize=args.diarize,
        max_chunk_minutes=args.max_chunk_minutes,
        keep_audio=args.keep_audio,
        quiet=args.quiet,
    )

    if args.output:
        args.output.write_text(transcript + "\n", encoding="utf-8")
        log(f"Transcript written to {args.output}", args.quiet)
    else:
        print(transcript)


if __name__ == "__main__":
    main()
