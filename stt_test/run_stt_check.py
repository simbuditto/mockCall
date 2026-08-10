#!/usr/bin/env python3
"""
Step 3 — Accent & vocabulary check.

Transcribes one or more short audio clips with Sarvam Saaras v3 and scores
whether the numbers and insurance jargon survived. General word-error rate is
ignored on purpose — only the terms that break STT matter here.

Usage:
    pip install sarvamai python-dotenv
    export SARVAM_API_KEY=...          # or put it in a .env file
    python stt_test/run_stt_check.py stt_test/*.wav

Each clip must be <= 30s (Saaras REST limit). For longer recordings, split them
or switch to the Batch API. WAV (16-bit PCM, mono, 16 kHz) gives best accuracy;
MP3/FLAC/OGG also work.

Output: per-clip transcript, a hit/miss table for the target terms, and a
ready-to-paste STT `prompt` line built from whatever was missed.
"""

import os
import re
import sys
import glob
import shutil
import tempfile
import subprocess

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from sarvamai import SarvamAI
except ImportError:
    sys.exit("Missing dependency. Run:  pip install sarvamai python-dotenv")

# Each target term: canonical label -> list of regex patterns that count as a hit.
# Patterns are matched case-insensitively against the transcript. Numbers include
# both digit and spelled-out forms because Saaras may normalise either way.
TARGETS = {
    "1.2 crore":            [r"1\.2\s*crore", r"one\s*point\s*two\s*crore", r"1,20,00,000", r"12000000", r"1\.2\s*cr"],
    "15-year term":         [r"15[\s-]*year", r"fifteen[\s-]*year"],
    "₹38,000 EMI":          [r"38[,\s]*000", r"thirty[\s-]*eight\s*thousand", r"38k"],
    "₹12 lakh":             [r"12\s*lakh", r"twelve\s*lakh", r"1200000", r"12,00,000"],
    "sum assured":          [r"sum\s*assured"],
    "premium paying term":  [r"premium\s*paying\s*term"],
    "endowment":            [r"endowment"],
    "ULIP":                 [r"ulip", r"u\.?l\.?i\.?p"],
    "rider":                [r"rider"],
    "nominee":              [r"nominee"],
    "lapse":                [r"lapse"],
    "maturity benefit":     [r"maturity\s*benefit"],
    "IRDAI":                [r"irdai", r"i\.?r\.?d\.?a\.?i", r"irda"],
    "term plan":            [r"term\s*plan"],
}


def score(transcript: str):
    t = transcript.lower()
    hits, misses = [], []
    for label, patterns in TARGETS.items():
        if any(re.search(p, t) for p in patterns):
            hits.append(label)
        else:
            misses.append(label)
    return hits, misses


def prepare_wav(path: str):
    """Return (wav_path, is_temp). Converts any non-WAV input to 16 kHz mono
    16-bit WAV so Sarvam always gets a MIME type it accepts. Voice Memos .m4a
    files report as audio/mp4a-latm, which the API rejects — converting avoids
    the whole problem and also gives best accuracy. Uses afconvert (built into
    macOS) or ffmpeg; if neither exists, sends the file as-is."""
    if path.lower().endswith(".wav"):
        return path, False
    out = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    if shutil.which("afconvert"):
        cmd = ["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", path, out]
    elif shutil.which("ffmpeg"):
        cmd = ["ffmpeg", "-y", "-i", path, "-ac", "1", "-ar", "16000",
               "-c:a", "pcm_s16le", out]
    else:
        return path, False  # no converter; try the original and hope
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return out, True


def transcribe(client, path: str) -> str:
    with open(path, "rb") as f:
        resp = client.speech_to_text.transcribe(
            file=f,
            model="saaras:v3",
            mode="transcribe",
            language_code="en-IN",   # advisor speaks English; skip detection
        )
    # SDK returns an object with .transcript; fall back to dict access just in case.
    return getattr(resp, "transcript", None) or resp["transcript"]


def main():
    files = []
    for arg in sys.argv[1:]:
        files.extend(sorted(glob.glob(arg)))
    files = [f for f in files if os.path.isfile(f)]
    if not files:
        sys.exit("No audio files. Usage: python stt_test/run_stt_check.py stt_test/*.wav")

    key = os.getenv("SARVAM_API_KEY")
    if not key:
        sys.exit("Set SARVAM_API_KEY (env var or .env file).")

    client = SarvamAI(api_subscription_key=key)

    all_missed = set()
    succeeded = 0
    for path in files:
        print("\n" + "=" * 74)
        print(f"CLIP: {path}")
        print("=" * 74)
        wav_path, is_temp = path, False
        try:
            wav_path, is_temp = prepare_wav(path)
            transcript = transcribe(client, wav_path)
        except Exception as e:
            print(f"  ERROR transcribing: {e}")
            continue
        finally:
            if is_temp and os.path.exists(wav_path):
                os.remove(wav_path)
        succeeded += 1
        print(f"\nTranscript:\n  {transcript}\n")
        hits, misses = score(transcript)
        print(f"  HIT  ({len(hits)}/{len(TARGETS)}): {', '.join(hits) or '—'}")
        print(f"  MISS ({len(misses)}/{len(TARGETS)}): {', '.join(misses) or '—'}")
        all_missed.update(misses)

    print("\n" + "#" * 74)
    if succeeded == 0:
        print("No clips transcribed successfully — see the errors above.")
        print("#" * 74)
        return
    if all_missed:
        print("TERMS MISSED ACROSS ALL CLIPS — feed these into the STT prompt (Step 5):")
        print("  " + ", ".join(sorted(all_missed)))
        print("\nSuggested STT prompt addition:")
        terms = ", ".join(sorted(all_missed))
        print(f'  "Indian insurance advisor speaking English. Expect terms like {terms}."')
    else:
        print("No misses. Saaras handled every target term. Still keep these recordings")
        print("as your regression corpus for when you change anything.")
    print("#" * 74)


if __name__ == "__main__":
    main()
