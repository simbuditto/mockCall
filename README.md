# Mock-Call Training Platform

A browser-based voice trainer for insurance advisors. The advisor picks one of
**three believable AI health-insurance customers**, confirms a microphone, and then
practises a discovery conversation. The transcript is saved and the cost breakdown is
available on request. Built as a working prototype to prove the pipeline, the
economics, and the path to a full system.

- **Stack:** Pipecat (orchestration) · Sarvam Saaras v3 (STT) · Claude Haiku 4.5 (LLM persona) · Sarvam Bulbul v3 (TTS)
- **Interface:** one HTML page with three pre-call stages — profile picker → mic-confirm → call UI (push-to-talk, live transcript, stats on demand)
- **Output:** per-call JSON transcript + goal checklist, per-turn cost CSV, validated ₹ cost summary

---

## Architecture

```
Browser (WebRTC, push-to-talk, mic select)
      │  audio
      ▼
   Pipecat pipeline ──────────────────────────────────────────────┐
      Sarvam Saaras v3 (STT)  →  Claude Haiku 4.5 (persona)  →  Sarvam Bulbul v3 (TTS)
      │                                                            │
      └─ observers (beside the pipeline): usage metering ─────────┘
      ▼  audio + transcript events
Browser  →  live transcript, countdown, cost card
On end   →  transcripts/<ts>.json (transcript + checklist + usage), usage/<ts>.csv
```

The two AI-cost observers sit *beside* the pipeline, never in the audio path, so
metering can never add latency.

---

## Repository layout

| Path | What it is |
|---|---|
| `bot.py` | The Pipecat voice bot: STT → LLM → TTS, session lifecycle, 5-min cap |
| `persona.py` | Loads a persona JSON and renders it into the system prompt |
| `usage.py` | Cost accumulator + observers (usage metering, transcript is read from context) |
| `persistence.py` | Writes the per-call transcript + checklist + usage JSON |
| `generate_fallback.py` | Pre-renders the "couldn't hear you" WAV in the persona voice |
| `index.html` | The entire frontend (vanilla JS, Pipecat web client via CDN) |
| `personas/*.json` | The three customers: surface concern, hidden facts, health profile, scripted lines, triggered questions, goal checklist |
| `profiles.json` | Landing-page catalogue: id + short summary the frontend renders for the picker |
| `QA_CHECKLIST.md` | Manual UX checks a human ticks after `scripts/verify.sh` passes |
| `rates.json` | Auditable per-unit pricing (STT/TTS/LLM) with a `verified_on` date |
| `contract.md` | The client⇄server event contract |
| `stt_test/` | The STT accent/vocabulary check (paragraph + scoring script) |
| `mock-call-build-plan.md` | The original two-day build plan this repo follows |
| `In-House_Mock_Call_Proposal.pdf` | Cost/capability proposal (vendor vs in-house) |

---

## Prerequisites

- Python 3.10+ and `pip`
- A **Sarvam** API key (dashboard.sarvam.ai) and an **Anthropic** API key (console.anthropic.com)
- A modern browser (Chrome/Edge/Safari) with a microphone

---

## Setup

```bash
git clone <your-repo-url> mockcall
cd mockcall

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # then edit .env and paste your two keys
```

**Sanity-check the install** (guards a known Pipecat/`sarvamai` version pin):

```bash
pip show sarvamai | grep -i version
python -c "from pipecat.services.sarvam.stt import SarvamSTTService; print('ok')"
```

`ok` means you're good.

---

## Run

Two terminals from the project root, with the venv active in both.

```bash
# Terminal 1 — one bot per persona, each on its own port (see profiles.json)
./run_bots.sh

# Terminal 2 — serve the frontend (localhost is a secure context, so mic works)
python -m http.server 8000
```

Each persona runs its own `bot.py` (rohan 7860, naveen 7861, rajesh 7862); the
landing page routes the chosen customer to the matching port. To run a single
persona for quick testing:
`PERSONA_PATH=personas/naveen_v1.json python bot.py --port 7861`.

Open **http://localhost:8000/** and walk the three pre-call stages:

1. **Pick a customer** from the three profile cards on the landing page.
2. **Confirm your microphone** on the device-setup card (Start Call stays
   disabled until you click *Confirm microphone*).
3. **Click Start Call.** The chosen customer greets you first; **hold the mic
   button (or Space) to talk**, release when done. Click **End Call** to finish.

When the call ends, the transcript stays put. Click **Show session stats** at
the bottom of the transcript to render the ₹ cost card on demand.

Optional, one-time:

```bash
python generate_fallback.py        # renders fallback.wav in Rohan's voice
```

Config knobs (via `.env` or inline): `MAX_CALL_SECONDS`, `PERSONA_PATH`
(fallback persona when the browser doesn't send a `persona_id`), `PERSONAS_DIR`.

---

## How it works

- **Personas as data.** `personas/*.json` holds each customer's surface concern,
  hidden facts, objections, a goal checklist, and a `voice_id`. Health personas
  add an optional `health_profile`, an `opening_line`, `scripted_lines` (stock
  answers), `triggered_questions` (the only questions the customer initiates,
  each on its own trigger), and `scripted_answers` (underwriting lines given only
  when asked). `persona.py` renders the chosen one into a system prompt whose core
  rule is *reveal a hidden fact only when the advisor asks a question that would
  surface it.*
- **Profile routing (per-port).** The landing page reads `profiles.json` to list
  the three customers. Because the SmallWebRTC client can only be handed a
  `webrtcUrl`, each persona runs its **own `bot.py` on a dedicated port** (via
  `run_bots.sh`), and the browser connects to the chosen persona's port. See
  `contract.md`.
- **The pipeline.** `bot.py` wires Sarvam STT → Claude Haiku (persona, prompt
  caching on, short-answer cap) → Sarvam TTS (`voice_id` = the persona's Bulbul v3
  speaker) over Pipecat's WebRTC transport.
- **Usage metering.** `usage.py` reads Pipecat's metrics frames from an observer
  and prices them from `rates.json`. Input tokens are split into fresh / cached /
  cache-write so the LLM isn't mis-costed. STT is measured as client mic-hold
  time (matches vendor billing far better than stream duration).
- **Persistence.** On end (advisor End, or the 5-minute cap), `persistence.py`
  writes `transcripts/<ts>.json` — the full transcript, the goal checklist, the
  usage summary, and the end reason — for trainer review.
- **Cost card, on request.** When a call ends the frontend does *not* auto-render
  the cost card — it appends a **Show session stats** button. Clicking it
  fetches the just-written session and renders the ₹ breakdown, cache-hit rate,
  and cost per turn. This keeps the post-call view focused on the transcript
  unless the advisor asks for money detail.

---

## Cost model

Measured, validated against the Sarvam and Anthropic dashboards (Aug 2026):

| Component | Rate | Per-minute (measured) |
|---|---|---|
| STT — Saaras v3 | ₹30/hour | ₹0.50 |
| TTS — Bulbul v3 | ₹30 / 10k chars | ₹0.93 (dominant) |
| LLM — Haiku 4.5 | $1 / $5 per Mtok | ₹0.37 |
| **In-house total** | | **≈₹1.80/min** |

Against a vendor charging ₹6/min, that's a **~70% reduction**. Per-minute cost is
driven by how much is spoken (TTS), so the card is a live estimate — the vendor
dashboards remain the billing source of truth. Rates live in `rates.json` with a
`verified_on` date; re-check them periodically.

---

## The build process that was followed

Built over a weekend against `mock-call-build-plan.md`. Strictly ordered; each
step had an acceptance test.

**Saturday**
1. Accounts and API keys (Sarvam + Anthropic).
2. Write the persona and goal checklist (`personas/ramesh_v1.json`) — the highest-value step; the persona *is* the product.
3. STT accent/vocabulary check (`stt_test/`) — verify Sarvam gets the numbers and jargon (₹12 lakh, sum assured, IRDAI…) right.
4. Environment + the `sarvamai` version trap (venv, install, import check).
5. Baseline pipeline — audio in, audio out (`bot.py`, generic assistant).
6. Persona layer — replace the assistant with the customer; reveal-only-when-asked; prompt caching.
7. Prompt iteration round one — talk to it, fix role-bleed and over-talking.
   → **Checkpoint 1:** a terminal/browser call that feels like a real customer.

**Sunday**
8. Event contract (`contract.md`) — the client⇄server message shapes.
9. Usage accumulator (`usage.py`, `rates.json`) — meter every call, per-turn CSV.
10. Session end + persistence (`persistence.py`) — transcript + checklist to disk; 5-minute cap.
    → **Checkpoint 2:** full loop headless.
11. Browser frontend (`index.html`) — WebRTC, push-to-talk, transcript pane, mic selector.
12. Cost summary card — ₹ breakdown, cache-hit rate, cost per turn.
13. Failure handling — garbled-input line, LLM retry, error banner, pre-rendered fallback WAV.
14. Prompt iteration round two — three full calls, persona-only fixes.
15. Validate the cost figures against both vendor dashboards — caught and fixed a 3× STT rate error and switched STT to mic-hold time.
    → **Checkpoint 3:** believable customer, manual end + cap, transcript-with-checklist, validated cost — all from the browser.

---

## Notes & caveats

- **Cache hit shows 0% by design.** Haiku 4.5's minimum cacheable prompt is ~4,096
  tokens; the compact persona is shorter, so nothing caches — and padding it would
  *raise* cost. LLM is already the cheapest line.
- **TTS cost is a slight under-estimate.** We count raw characters; Bulbul bills
  normalized characters (~30% more). Treat the dashboards as billing truth.
- **One session at a time** in V1. Concurrency, auth, and a database are the first
  production additions (the service is already stateless).

---

## Roadmap (V2)

Automatic goal-detection & auto-end · scoring rubric · post-call feedback pass ·
persona library · trainer dashboard · shared transcript format for live-call QA
automation. Each extends the existing building blocks — none needs a rewrite.

---

## Version history

**v1.2 — Health-insurance persona set** (Aug 2026)
- **Replaced the persona library** with three health-insurance customers drawn
  from the field-team briefs: **Rohan** (wellness/fitness benefits, no PED but a
  high BMI), **Naveen** (family floater for a newborn with a congenital
  condition), and **Rajesh** (first-time buyer for self + spouse, hypothyroid with
  an old kidney-stone surgery). The earlier life-insurance five were retired.
- **Richer persona schema.** `persona.py` now renders optional `health_profile`,
  `opening_line`, `scripted_lines`, `triggered_questions` (customer-initiated
  questions, each on its trigger condition), and `scripted_answers` (underwriting
  lines given only when the matching question is asked), on top of the existing
  fields — so the customer follows the briefs' scripted turns instead of only
  reacting.
- **Routing + gate updated:** `profiles.json` and `run_bots.sh` now list three
  personas (rohan 7860, naveen 7861, rajesh 7862); `scripts/verify.sh` requires
  three personas (was five).

**v1.1 — Multi-persona + guided pre-call flow** (`feature/automation`, Aug 2026)
- **Five customer profiles** chosen on a landing page — Priya (young single earner),
  Ramesh (family breadwinner), Vikram (HNI), Krishnamurthy (near-retirement), and
  Suresh (hardened sceptic) — each authored as data in `personas/*.json`.
- **Microphone selection now happens before the session**, with an explicit
  *Confirm microphone* step; Start Call stays disabled until it's confirmed.
- **Session stats are shown only on request** — the cost card no longer appears
  automatically at call end; a **Show session stats** button reveals it.
- **Per-port persona routing** (`run_bots.sh`): one `bot.py` per persona on its own
  port, replacing an earlier attempt to pass `persona_id` through the WebRTC offer
  (which the SmallWebRTC client silently ignores).
- **Voice fix:** TTS now uses the `voice_id` kwarg (the previous `speaker=` was
  ignored, so every persona spoke in the default voice); each persona has a
  distinct, validated Bulbul v3 speaker.
- **Automation harness:** `TASKS.md` (spec), `scripts/verify.sh` (the checks gate,
  now including voice-ID validation), `CLAUDE.md`, and a GitHub Actions workflow.

**v1.0 — Working prototype** (`main`, Aug 2026)
- Single customer (Ramesh) spoken mock call end-to-end in the browser: Sarvam STT →
  Claude Haiku persona → Sarvam TTS over WebRTC, push-to-talk.
- Manual End plus a 5-minute cap; per-call transcript + goal checklist saved to disk.
- Usage metering priced from `rates.json`, validated against vendor dashboards
  (caught and fixed a 3× STT rate error; STT measured as mic-hold time).
- Two-page cost/capability proposal (`In-House_Mock_Call_Proposal.pdf`).

---

## Security

`.env` is gitignored and must never be committed. If a key is ever exposed, rotate
it in the vendor dashboard. Transcripts and usage logs are gitignored (they contain
call content) and stay local.
