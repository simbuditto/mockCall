"""
Step 13 — pre-generate the fallback WAV.

A TTS failure cannot be announced by TTS, so we synthesise the "couldn't hear
you" line ONCE, in the customer's own voice, and keep the file on disk. Run this
whenever you change the persona voice:

    python generate_fallback.py

It writes fallback.wav in the customer's voice (persona voice_id).
"""

import os
import json
import base64

from dotenv import load_dotenv
from sarvamai import SarvamAI

load_dotenv()

FALLBACK_LINE = "Sorry, I couldn't hear you. Can you please repeat that?"
PERSONA_PATH = os.getenv("PERSONA_PATH", "personas/rohan_v1.json")


def main():
    key = os.getenv("SARVAM_API_KEY")
    if not key:
        raise SystemExit("Set SARVAM_API_KEY (env var or .env).")

    persona = json.load(open(PERSONA_PATH, encoding="utf-8"))
    speaker = persona.get("voice_id", "rahul")

    client = SarvamAI(api_subscription_key=key)
    resp = client.text_to_speech.convert(
        language_code="en-IN",
        text=FALLBACK_LINE,
        model="bulbul:v3",
        speaker=speaker,
    )
    wav = base64.b64decode("".join(resp.audios))
    with open("fallback.wav", "wb") as f:
        f.write(wav)
    print(f"wrote fallback.wav ({len(wav)} bytes) in voice '{speaker}'")


if __name__ == "__main__":
    main()
