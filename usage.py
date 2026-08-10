"""
Step 9 — Usage accumulator.

Counts what the call actually consumed and turns it into rupees at the end.
Two pieces:

  UsageAccumulator  — pure Python, no Pipecat. Holds counters, computes INR
                      totals from rates.json, writes a per-turn CSV. Unit-testable
                      on its own (see __main__).

  UsageObserver     — a Pipecat observer that reads MetricsFrame off the pipeline
                      and feeds the accumulator. An observer sits BESIDE the
                      pipeline, never in the audio path (plan gotcha #10).

Token accounting (Anthropic): input arrives in three buckets billed at different
rates — fresh (base), cache_read (~0.1x), cache_creation/write (~1.25x). We keep
them separate; lumping them makes the LLM look ~10x too expensive (plan gotcha #8).
Counts come straight from the API usage block via Pipecat metrics — never
estimated with a tokenizer (gotcha #9).
"""

import os
import csv
import json
import time
from datetime import datetime, timezone


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


class UsageAccumulator:
    def __init__(self, rates_path="rates.json", csv_dir="usage", session_id=None):
        with open(rates_path, "r", encoding="utf-8") as f:
            self.rates = json.load(f)

        self.session_id = session_id or time.strftime("%Y-%m-%d-%H%M%S")
        self.csv_dir = csv_dir
        self._csv_file = None
        self._csv_writer = None

        # Running totals for the whole call.
        self.stt_seconds = 0.0
        self.tts_chars = 0
        self.llm_fresh = 0          # prompt_tokens (net of cache)
        self.llm_cache_read = 0     # cache_read_input_tokens
        self.llm_cache_write = 0    # cache_creation_input_tokens
        self.llm_output = 0         # completion_tokens
        self.turns = 0

        # Deltas for the turn currently in progress (flushed to CSV per turn).
        self._t = self._empty_turn()

        self.start_time = time.monotonic()

    # ---- ingest (called by the observer, or the client for STT hold-time) ----

    def add_stt_seconds(self, seconds: float):
        self.stt_seconds += seconds
        self._t["stt_seconds"] += seconds

    def add_tts_chars(self, chars: int):
        self.tts_chars += chars
        self._t["tts_chars"] += chars

    def add_llm(self, fresh=0, cache_read=0, cache_write=0, output=0):
        self.llm_fresh += fresh
        self.llm_cache_read += cache_read
        self.llm_cache_write += cache_write
        self.llm_output += output
        self._t["llm_fresh"] += fresh
        self._t["llm_cache_read"] += cache_read
        self._t["llm_cache_write"] += cache_write
        self._t["llm_output"] += output

    def flush_turn(self):
        """Write the in-progress turn as a CSV row and reset. Skips empty turns
        (e.g. spurious boundary before any metrics arrived)."""
        t = self._t
        if not any([t["stt_seconds"], t["tts_chars"], t["llm_fresh"],
                    t["llm_cache_read"], t["llm_cache_write"], t["llm_output"]]):
            return
        self.turns += 1
        cost = self._cost(t["stt_seconds"], t["tts_chars"], t["llm_fresh"],
                          t["llm_cache_read"], t["llm_cache_write"], t["llm_output"])
        self._write_csv_row({
            "turn": self.turns,
            "stt_seconds": round(t["stt_seconds"], 2),
            "tts_chars": t["tts_chars"],
            "llm_fresh": t["llm_fresh"],
            "llm_cache_read": t["llm_cache_read"],
            "llm_cache_write": t["llm_cache_write"],
            "llm_output": t["llm_output"],
            "cost_inr": cost["total"],
        })
        self._t = self._empty_turn()

    # ---- cost math ----

    def _cost(self, stt_seconds, tts_chars, fresh, cache_read, cache_write, output):
        r = self.rates
        stt = (stt_seconds / 60.0) * r["stt"]["rate"]
        tts = (tts_chars / 10000.0) * r["tts"]["rate"]
        llm = r["llm"]
        llm_usd = (
            fresh / 1e6 * llm["input"]
            + cache_read / 1e6 * llm["cache_read"]
            + cache_write / 1e6 * llm.get("cache_write", llm["input"])
            + output / 1e6 * llm["output"]
        )
        llm_inr = llm_usd * r["usd_to_inr"]
        return {
            "stt": round(stt, 2),
            "tts": round(tts, 2),
            "llm": round(llm_inr, 2),
            "total": round(stt + tts + llm_inr, 2),
        }

    def summary(self) -> dict:
        cost = self._cost(self.stt_seconds, self.tts_chars, self.llm_fresh,
                          self.llm_cache_read, self.llm_cache_write, self.llm_output)
        total_input = self.llm_fresh + self.llm_cache_read + self.llm_cache_write
        cache_hit_rate = (self.llm_cache_read / total_input) if total_input else 0.0
        return {
            "turns": self.turns,
            "elapsed_seconds": round(time.monotonic() - self.start_time, 1),
            "stt_seconds": round(self.stt_seconds, 1),
            "tts_chars": self.tts_chars,
            "llm_input_fresh_tokens": self.llm_fresh,
            "llm_input_cached_tokens": self.llm_cache_read,
            "llm_input_cache_creation_tokens": self.llm_cache_write,
            "llm_output_tokens": self.llm_output,
            "cache_hit_rate": round(cache_hit_rate, 3),
            "cost_inr": cost,
        }

    def close(self):
        if self._csv_file:
            self._csv_file.close()
            self._csv_file = None

    # ---- internals ----

    @staticmethod
    def _empty_turn():
        return {"stt_seconds": 0.0, "tts_chars": 0, "llm_fresh": 0,
                "llm_cache_read": 0, "llm_cache_write": 0, "llm_output": 0}

    def _write_csv_row(self, row: dict):
        if self._csv_writer is None:
            os.makedirs(self.csv_dir, exist_ok=True)
            path = os.path.join(self.csv_dir, f"{self.session_id}.csv")
            self._csv_file = open(path, "w", newline="", encoding="utf-8")
            self._csv_writer = csv.DictWriter(self._csv_file, fieldnames=list(row.keys()))
            self._csv_writer.writeheader()
        self._csv_writer.writerow(row)
        self._csv_file.flush()


# --------------------------------------------------------------------------
# Pipecat observer. Imports guarded so this module still loads (and the
# accumulator self-test still runs) in an environment without Pipecat.
# --------------------------------------------------------------------------
try:
    from pipecat.observers.base_observer import BaseObserver
    from pipecat.frames.frames import (
        MetricsFrame,
        BotStoppedSpeakingFrame,
        TranscriptionFrame,
        TTSTextFrame,
    )
    from pipecat.metrics.metrics import (
        LLMUsageMetricsData,
        TTSUsageMetricsData,
        STTUsageMetricsData,
    )
    _PIPECAT = True
except ImportError:
    BaseObserver = object
    _PIPECAT = False


class UsageObserver(BaseObserver):
    """Reads usage metrics off the pipeline and feeds the accumulator. Dedupes on
    frame id because a frame is observed on every processor hop it makes."""

    def __init__(self, accumulator: UsageAccumulator, **kwargs):
        if _PIPECAT:
            super().__init__(**kwargs)
        self.acc = accumulator
        self._seen = set()

    async def on_push_frame(self, data):
        frame = data.frame
        fid = id(frame)
        if isinstance(frame, MetricsFrame):
            if fid in self._seen:
                return
            self._seen.add(fid)
            for m in frame.data:
                if isinstance(m, LLMUsageMetricsData):
                    u = m.value
                    self.acc.add_llm(
                        fresh=u.prompt_tokens or 0,
                        cache_read=u.cache_read_input_tokens or 0,
                        cache_write=u.cache_creation_input_tokens or 0,
                        output=u.completion_tokens or 0,
                    )
                elif isinstance(m, TTSUsageMetricsData):
                    self.acc.add_tts_chars(m.value or 0)
                elif isinstance(m, STTUsageMetricsData):
                    self.acc.add_stt_seconds(m.value.audio_seconds or 0.0)
        elif isinstance(frame, BotStoppedSpeakingFrame):
            # Customer finished a reply → STT+LLM+TTS for this turn have passed.
            if fid in self._seen:
                return
            self._seen.add(fid)
            self.acc.flush_turn()


class TranscriptObserver(BaseObserver):
    """Collects a role-labelled, timestamped transcript from the frame stream.

    Advisor turns come from final TranscriptionFrames (STT). Customer turns are
    assembled from the TTSTextFrame chunks spoken between successive
    BotStoppedSpeakingFrames. Runs beside the pipeline, not in it.
    """

    def __init__(self, out_list, **kwargs):
        if _PIPECAT:
            super().__init__(**kwargs)
        self.lines = out_list
        self._seen = set()
        self._bot_buf = []

    async def on_push_frame(self, data):
        frame = data.frame
        fid = id(frame)
        if fid in self._seen:
            return

        if isinstance(frame, TranscriptionFrame):
            self._seen.add(fid)
            text = (frame.text or "").strip()
            if text:
                self.lines.append({
                    "speaker": "advisor", "text": text, "timestamp": _now_iso()
                })
        elif isinstance(frame, TTSTextFrame):
            self._seen.add(fid)
            if frame.text:
                self._bot_buf.append(frame.text)
        elif isinstance(frame, BotStoppedSpeakingFrame):
            self._seen.add(fid)
            text = " ".join(self._bot_buf).strip()
            self._bot_buf = []
            if text:
                self.lines.append({
                    "speaker": "customer", "text": text, "timestamp": _now_iso()
                })


if __name__ == "__main__":
    # Self-test the cost math with the plan's example numbers (rates.json).
    acc = UsageAccumulator()
    # One synthetic turn resembling a real one.
    acc.add_stt_seconds(154.0)
    acc.add_tts_chars(2980)
    acc.add_llm(fresh=2100, cache_read=21400, cache_write=1200, output=1050)
    acc.flush_turn()
    import pprint
    pprint.pprint(acc.summary())
    acc.close()
