"""
Clone the founder's voice with ElevenLabs (Instant Voice Cloning) and wire it into
the journey pipeline.

Usage:
  # from engine/ with the epifani-growth env active
  python tools/clone_voice.py path/to/sample.mp3 [more_samples.wav ...]
  python tools/clone_voice.py --name "Founder" sample.mp3
  python tools/clone_voice.py --test sample.mp3        # also render a test line
  python tools/clone_voice.py --no-env-update sample.mp3   # don't touch .env

What it does:
  1. Uploads your voice sample(s) to ElevenLabs Instant Voice Cloning (/v1/voices/add).
  2. Prints the new voice_id.
  3. Unless --no-env-update, rewrites ELEVENLABS_VOICE_ID in engine/.env (a .env.bak
     backup is written first) so every future journey video uses YOUR voice — no
     other code change needed.
  4. With --test, synthesizes a short line to assets/output/voice_clone_test.mp3 so
     you can hear it immediately.

Sample tips: 1–3 minutes of clean speech, quiet room, your normal (slightly upbeat)
speaking energy. One good file beats several noisy ones. MP3 or WAV.

NOTE ON PLANS: Instant Voice Cloning generally requires a paid ElevenLabs plan
(Starter, ~$5/mo). On the free tier the API will reject /voices/add with a
permission error (401/403) — the script detects this and tells you. That $5/mo is
the one paid dependency for using your real voice; everything else stays free.
"""
import argparse
import sys
from pathlib import Path

import requests
from dotenv import dotenv_values

ENG = Path(__file__).resolve().parent.parent
ENV_PATH = ENG / ".env"
API_ADD = "https://api.elevenlabs.io/v1/voices/add"


def _api_key() -> str:
    key = (dotenv_values(ENV_PATH).get("ELEVENLABS_API_KEY") or "").strip()
    if not key:
        sys.exit(f"✗ ELEVENLABS_API_KEY not set in {ENV_PATH}")
    return key


def clone(samples: list[Path], name: str, api_key: str) -> str:
    for s in samples:
        if not s.exists():
            sys.exit(f"✗ Sample not found: {s}")
    print(f"⬆  Uploading {len(samples)} sample(s) to ElevenLabs as '{name}'...")
    files = [("files", (s.name, s.open("rb"), "audio/mpeg")) for s in samples]
    data = {
        "name": name,
        "description": "Epifani founder — build-in-public journey videos",
    }
    resp = requests.post(API_ADD, headers={"xi-api-key": api_key},
                         data=data, files=files, timeout=180)
    if resp.status_code in (401, 403):
        sys.exit(
            "✗ ElevenLabs rejected the clone (permission).\n"
            "  Instant Voice Cloning needs a paid plan (Starter, ~$5/mo).\n"
            "  Upgrade at elevenlabs.io, then re-run this script.\n"
            f"  Server said: {resp.text[:300]}"
        )
    if not resp.ok:
        sys.exit(f"✗ Clone failed ({resp.status_code}): {resp.text[:400]}")
    voice_id = resp.json().get("voice_id")
    if not voice_id:
        sys.exit(f"✗ No voice_id in response: {resp.text[:400]}")
    print(f"✓ Cloned. New voice_id: {voice_id}")
    return voice_id


def update_env(voice_id: str) -> None:
    text = ENV_PATH.read_text(encoding="utf-8")
    (ENG / ".env.bak").write_text(text, encoding="utf-8")
    lines, replaced = [], False
    for line in text.splitlines():
        if line.strip().startswith("ELEVENLABS_VOICE_ID="):
            lines.append(f"ELEVENLABS_VOICE_ID={voice_id}")
            replaced = True
        else:
            lines.append(line)
    if not replaced:
        lines.append(f"ELEVENLABS_VOICE_ID={voice_id}")
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"✓ Wrote ELEVENLABS_VOICE_ID to {ENV_PATH} (backup: .env.bak)")


def test_line(voice_id: str, api_key: str) -> None:
    """Synthesize a short line so you can hear the clone (uses a little quota)."""
    out = ENG / "assets" / "output" / "voice_clone_test.mp3"
    out.parent.mkdir(parents=True, exist_ok=True)
    model = (dotenv_values(ENV_PATH).get("ELEVENLABS_MODEL") or "eleven_v3").strip()
    line = ("Day two twenty of building Epifani. This is my actual voice now, "
            "and honestly it already feels way more real. Let's get into it.")
    print("🎙️  Rendering a test line...")
    r = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        headers={"xi-api-key": api_key, "Content-Type": "application/json"},
        json={"text": line, "model_id": model,
              "voice_settings": {"stability": 0.28, "similarity_boost": 0.75,
                                 "style": 0.65, "use_speaker_boost": True}},
        timeout=120,
    )
    if not r.ok:
        print(f"⚠ Test synth failed ({r.status_code}): {r.text[:300]}")
        return
    out.write_bytes(r.content)
    print(f"✓ Test voice: {out}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Clone the founder's voice via ElevenLabs.")
    ap.add_argument("samples", nargs="+", type=Path, help="audio sample file(s) (mp3/wav)")
    ap.add_argument("--name", default="Epifani Founder", help="voice name in ElevenLabs")
    ap.add_argument("--test", action="store_true", help="also render a test line")
    ap.add_argument("--no-env-update", action="store_true", help="don't rewrite .env")
    args = ap.parse_args()

    key = _api_key()
    voice_id = clone(args.samples, args.name, key)
    if not args.no_env_update:
        update_env(voice_id)
    if args.test:
        test_line(voice_id, key)
    print("\nDone. Next: re-render a journey video and it will use your voice.")


if __name__ == "__main__":
    main()
