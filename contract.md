# Event contract (V1)

The message shapes exchanged between the backend (`bot.py`) and the browser
frontend (Step 11). Written before the frontend so it doesn't drift mid-build.

## Transport — how this differs from the original plan

The plan sketched a raw WebSocket carrying base64 PCM audio in both directions.
We are instead on **Pipecat's WebRTC transport** (the `webrtc` runner), which
already carries microphone and bot audio as native media streams. So:

- **Audio is NOT our protocol.** getUserMedia capture, PCM encoding, playback,
  and the audio socket are all handled by the WebRTC transport + Pipecat client.
  There are no `audio_chunk` messages for us to define or manage.
- **We only define the app-event layer:** transcripts, session lifecycle, and the
  end-of-call usage summary. These travel as Pipecat app messages over the same
  peer connection's data channel.

This is why there is no `audio_chunk` entry below, unlike the original sketch.

## server → client

```jsonc
{ "type": "session_started",  "persona_name": "Ramesh Kulkarni", "persona_id": "ramesh_v1" }

{ "type": "user_transcript",  "text": "...", "final": true }   // advisor speech (STT)
{ "type": "bot_transcript",   "text": "..." }                  // customer speech (LLM)

{ "type": "session_ended",
  "reason": "ended_by_advisor",              // or "time_cap"
  "transcript_path": "transcripts/2026-08-10-1430.json",
  "usage_summary": {
    "turns": 12, "elapsed_seconds": 296,
    "stt_seconds": 154.0, "tts_chars": 2980,
    "llm_input_fresh_tokens": 2100, "llm_input_cached_tokens": 21400,
    "llm_output_tokens": 1050,
    "cost_inr": { "stt": 3.85, "tts": 8.94, "llm": 2.40, "total": 15.19 }
  }
}

{ "type": "error", "message": "..." }
```

## client → server

```jsonc
// The `persona_id` is not an app-event message — it's threaded through the
// WebRTC offer's requestData, so the bot has the right persona loaded before
// the pipeline even starts. See "Persona selection" below.
{ "type": "end_session" }                                 // advisor clicks End Call
```

## Persona selection

The browser picks one of the five customer profiles (see `profiles.json`) on
the landing page. That `persona_id` is sent to the bot at connect time via the
Pipecat client's `webrtcRequestParams.requestData`:

```js
await pc.connect({
  webrtcRequestParams: {
    endpoint: "http://localhost:7860/api/offer",
    requestData: { persona_id: "ramesh_v1" }
  },
});
```

The Pipecat runner surfaces that payload on `runner_args.body`. `bot.py`
resolves it to a file under `personas/` (whitelist-checked to block path
traversal) and falls back to the `PERSONA_PATH` env var when the id is
missing, malformed, or unknown — so raw `curl` calls and older clients keep
working. The persona load happens once per session, before the pipeline is
built.

## Notes

- **No `goal_progress` message in V1.** Nothing tracks checklist coverage yet —
  that's the deferred auto-detection feature (V2). The checklist is attached to
  the saved transcript instead, for the trainer to tick by eye.
- **`final` on `user_transcript`:** only `final: true` transcripts feed the LLM.
  Partials (`final: false`), if surfaced at all, are for the on-screen transcript
  only — never sent to the model. (Gotcha #3.)
- **Timestamps & speaker labels** live in the saved transcript JSON (Step 10), not
  in the streamed transcript messages.
```
