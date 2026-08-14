"""
Step 5 — Baseline pipeline. Audio in, audio out. Nothing else yet.

Sarvam Saaras v3 (STT) → Claude Haiku 4.5 (LLM) → Sarvam Bulbul v3 (TTS),
over Pipecat's local WebRTC transport. No telephony, no persona yet — the
persona layer arrives in Step 6.

Run:
    source .venv/bin/activate
    python bot.py
Then open the URL it prints (http://localhost:7860 by default), click Connect,
and talk. You should hear a voice answer. Content doesn't matter at this step.

If this misbehaves, sanity-check your environment against Pipecat's own stock
Sarvam example before blaming this file:
    git clone https://github.com/pipecat-ai/pipecat-examples.git
    # run the sarvam sample under examples/foundational/ with your keys
"""

import os
import json
import time
import asyncio

from dotenv import load_dotenv
from loguru import logger

from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask, PipelineParams
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
)
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.services.anthropic.llm import AnthropicLLMService
from pipecat.services.sarvam.stt import SarvamSTTService
from pipecat.services.sarvam.tts import SarvamTTSService
from pipecat.transports.base_transport import TransportParams

from persona import load_persona, render_system_prompt
from usage import UsageAccumulator, UsageObserver
from persistence import save_session

load_dotenv(override=True)

PERSONA_PATH = os.getenv("PERSONA_PATH", "personas/ramesh_v1.json")
PERSONAS_DIR = os.getenv("PERSONAS_DIR", "personas")
# 5-minute hard cap as a backstop against a forgotten open session (config, not
# inline — you'll want to change it; see the note in the plan's Reference section).
MAX_CALL_SECONDS = int(os.getenv("MAX_CALL_SECONDS", "300"))


def _resolve_persona_path(persona_id: str | None) -> str:
    """Map a client-supplied persona_id to a persona file inside PERSONAS_DIR.

    Falls back to PERSONA_PATH when the id is missing, malformed, or unknown.
    Guards against path traversal — only bare ids like "ramesh_v1" are accepted.
    """
    if not persona_id or not isinstance(persona_id, str):
        return PERSONA_PATH
    # Bare-id whitelist: letters, digits, underscore, hyphen. No slashes, no dots.
    if not persona_id.replace("_", "").replace("-", "").isalnum():
        logger.warning(f"Rejecting suspicious persona_id: {persona_id!r}")
        return PERSONA_PATH
    candidate = os.path.join(PERSONAS_DIR, f"{persona_id}.json")
    if os.path.isfile(candidate):
        return candidate
    logger.warning(f"Unknown persona_id {persona_id!r}, falling back to {PERSONA_PATH}")
    return PERSONA_PATH


def _message_text(content) -> str:
    """Flatten an LLM message's content (string or list of parts) to plain text."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for p in content:
            if isinstance(p, dict) and p.get("type") == "text":
                parts.append(p.get("text", ""))
            elif isinstance(p, str):
                parts.append(p)
        return " ".join(parts).strip()
    return ""


def build_transcript(context) -> list:
    """Turn the LLM context into a role-labelled transcript. user -> advisor
    (the trainee at the mic), assistant -> customer (Ramesh). System messages
    are skipped."""
    lines = []
    for m in context.get_messages():
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        if role not in ("user", "assistant"):
            continue
        text = _message_text(m.get("content"))
        if not text:
            continue
        lines.append({
            "turn": len(lines) + 1,
            "speaker": "advisor" if role == "user" else "customer",
            "text": text,
        })
    return lines

# Insurance jargon that STT should expect. From the Step 3 accent check — Saaras
# handled almost everything; this is a cheap safeguard for the domain terms.
STT_HINT_TERMS = (
    "Indian insurance advisor speaking English. Expect terms like sum assured, "
    "ULIP, rider, premium paying term, endowment, term plan, lakh, crore, LIC, "
    "IRDAI, nominee, maturity benefit."
)


async def bot(runner_args: RunnerArguments):
    """Main bot entry point (Pipecat runner convention)."""

    transport = await create_transport(
        runner_args,
        {
            "webrtc": lambda: TransportParams(
                audio_in_enabled=True, audio_out_enabled=True
            ),
        },
    )

    # --- Speech to text: Sarvam Saaras v3, advisor speaks English ---
    stt = SarvamSTTService(
        api_key=os.getenv("SARVAM_API_KEY"),
        language="en-IN",
        model="saaras:v3",
        mode="transcribe",
    )

    # --- Persona: load the customer Claude will play ---
    # The browser passes the chosen persona_id via SmallWebRTCRequest.requestData,
    # which the runner surfaces as runner_args.body. Absent/invalid ids fall back
    # to PERSONA_PATH so the server still works from a raw curl or older client.
    body = getattr(runner_args, "body", None) or {}
    persona_id = body.get("persona_id") if isinstance(body, dict) else None
    persona_path = _resolve_persona_path(persona_id)
    persona = load_persona(persona_path)
    system_prompt = render_system_prompt(persona)
    logger.info(f"Loaded persona: {persona['name']} ({persona['id']}) from {persona_path}")

    # --- LLM: Claude Haiku 4.5, persona-driven, prompt caching on ---
    llm = AnthropicLLMService(
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        settings=AnthropicLLMService.Settings(
            model="claude-haiku-4-5-20251001",
            enable_prompt_caching=True,   # persona block is re-sent every turn
            max_tokens=80,                # hard ceiling keeps replies short
        ),
        retry_on_timeout=True,            # retry once on a slow/failed call
        retry_timeout_secs=4.0,
    )

    # --- Text to speech: Sarvam Bulbul v3, voice from the persona file ---
    tts = SarvamTTSService(
        api_key=os.getenv("SARVAM_API_KEY"),
        language_code="en-IN",
        model="bulbul:v3",
        speaker=persona.get("voice_id", "rahul"),
        pace=1.0,
    )

    messages = [
        {"role": "system", "content": system_prompt},
    ]
    context = LLMContext(messages)
    context_aggregator = LLMContextAggregatorPair(context)

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            context_aggregator.user(),
            llm,
            tts,
            transport.output(),
            context_aggregator.assistant(),
        ]
    )

    # --- Shared session id ties the transcript JSON to the usage CSV ---
    session_id = time.strftime("%Y-%m-%d-%H%M%S")

    # --- Usage observer sits beside the pipeline, not in it. The transcript is
    #     read from the LLM context at end-of-call (authoritative for both
    #     speakers), so no transcript observer is needed. ---
    usage = UsageAccumulator(session_id=session_id)
    usage_observer = UsageObserver(usage)

    task = PipelineTask(
        pipeline,
        params=PipelineParams(enable_metrics=True, enable_usage_metrics=True),
        observers=[usage_observer],
    )

    # Shared end state so both end paths write exactly once.
    ended = {"done": False}
    cap_handle = {"task": None}

    async def end_session(reason: str):
        if ended["done"]:
            return
        ended["done"] = True
        if cap_handle["task"]:
            cap_handle["task"].cancel()

        usage.flush_turn()  # capture any turn in progress
        summary = usage.summary()
        transcript_lines = build_transcript(context)
        path = save_session(persona, transcript_lines, summary, reason,
                            session_id=session_id)
        usage.close()
        logger.info(f"Session ended ({reason}). Transcript: {path}")
        logger.info("=== CALL USAGE SUMMARY ===\n" + json.dumps(summary, indent=2))
        await task.cancel()

    async def cap_timer():
        try:
            await asyncio.sleep(MAX_CALL_SECONDS)
            logger.info(f"{MAX_CALL_SECONDS}s cap reached — ending call.")
            await end_session("time_cap")
        except asyncio.CancelledError:
            pass

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("Advisor joined — customer opens in character.")
        cap_handle["task"] = asyncio.create_task(cap_timer())
        messages.append(
            {
                "role": "system",
                "content": (
                    "The advisor has just joined the call. Say your opening line "
                    "in character: a brief greeting and your surface concern, in "
                    "one or two short sentences. Do not reveal anything else."
                ),
            }
        )
        await task.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Advisor disconnected.")
        await end_session("ended_by_advisor")

    runner = PipelineRunner(handle_sigint=runner_args.handle_sigint)
    await runner.run(task)


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
