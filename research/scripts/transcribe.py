#!/usr/bin/env python3
"""Transcribe downloaded Reel audio to .txt files.

Linux adaptation of the original transcribe.sh: uses faster-whisper
(CTranslate2 backend, no torch download) with a fallback to openai-whisper
if that's what's installed.

Usage: python3 scripts/transcribe.py <project-name> [--model tiny|base|small]
"""
import argparse
import sys
from pathlib import Path

AUDIO_EXTS = {".mp3", ".m4a", ".webm", ".opus", ".wav"}


def transcribe_faster_whisper(audio: Path, model_name: str, _cache={}) -> str:
    from faster_whisper import WhisperModel
    if model_name not in _cache:
        _cache[model_name] = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, _info = _cache[model_name].transcribe(str(audio), language="en")
    return " ".join(seg.text.strip() for seg in segments).strip()


def transcribe_openai_whisper(audio: Path, model_name: str, _cache={}) -> str:
    import whisper
    if model_name not in _cache:
        _cache[model_name] = whisper.load_model(model_name)
    result = _cache[model_name].transcribe(str(audio), language="en", fp16=False)
    return result["text"].strip()


def main():
    parser = argparse.ArgumentParser(description="Transcribe project Reel audio with Whisper")
    parser.add_argument("project", help="project name under projects/")
    parser.add_argument("--model", default="tiny", help="whisper model size (default: tiny)")
    args = parser.parse_args()

    transcripts_dir = Path(__file__).resolve().parent.parent / "projects" / args.project / "transcripts"
    if not transcripts_dir.is_dir():
        print(f"No transcripts directory found for project: {args.project}")
        sys.exit(1)

    try:
        import faster_whisper  # noqa: F401
        transcribe = transcribe_faster_whisper
        backend = "faster-whisper"
    except ImportError:
        try:
            import whisper  # noqa: F401
            transcribe = transcribe_openai_whisper
            backend = "openai-whisper"
        except ImportError:
            print("Neither faster-whisper nor openai-whisper is installed.")
            print("Install one:  pip install faster-whisper")
            sys.exit(1)

    audio_files = sorted(p for p in transcripts_dir.iterdir() if p.suffix.lower() in AUDIO_EXTS)
    todo = [p for p in audio_files if not p.with_suffix(".txt").exists()]

    print()
    print("========================================")
    print(f"  Transcribing {len(todo)} audio files ({backend}, model={args.model})")
    print(f"  Project: {args.project}")
    print(f"  Skipped (already done): {len(audio_files) - len(todo)}")
    print("========================================")
    print()

    done = failed = 0
    for i, audio in enumerate(todo, 1):
        print(f"  [{i}/{len(todo)}] {audio.stem}...")
        try:
            text = transcribe(audio, args.model)
            audio.with_suffix(".txt").write_text(text + "\n")
            done += 1
            print(f"    ok ({len(text.split())} words)")
        except Exception as e:
            failed += 1
            print(f"    FAILED: {e}")

    print()
    print("========================================")
    print(f"  Transcription complete!  ok: {done}  failed: {failed}")
    print("========================================")


if __name__ == "__main__":
    main()
