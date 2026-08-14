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
{ "type": "end_session" }                                 // advisor clicks End Call
```

## Persona selection (per-port routing)

The SmallWebRTC JS client's `connect()` accepts **only** a `webrtcUrl` — there is
no supported way to attach custom data (like a `persona_id`) to the WebRTC offer.
So persona selection is done by **routing to a different bot per persona**, each
running on its own port:

- Each persona runs its own `bot.py` process with `PERSONA_PATH` set to that
  persona file, on a dedicated port (see `run_bots.sh` and the `port` field in
  `profiles.json`): ramesh 7860, priya 7861, vikram 7862, krishnamurthy 7863,
  suresh 7864.
- The landing page reads `profiles.json`; when the advisor picks a profile the
  browser connects to that profile's port:

```js
await pc.connect({ webrtcUrl: `http://localhost:${profile.port}/api/offer` });
```

`bot.py` still supports a `persona_id` in `runner_args.body` (whitelisted, with a
`PERSONA_PATH` fallback) for future single-process routing via the RTVI `/start`
endpoint, but the working V1 mechanism is per-port.

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
