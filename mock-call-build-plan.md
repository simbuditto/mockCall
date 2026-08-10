# Mock-Call Training Platform — Solo Build Plan

**Builder:** one person. **Target:** working demo in two days.
**Stack:** Pipecat (orchestration) · Sarvam Saaras v3 (STT) · Sarvam Bulbul v3 (TTS) · Claude Haiku 4.5 (LLM)

> API signatures below are indicative. Pipecat and Sarvam both move fast — verify
> against `docs.pipecat.ai` and `docs.sarvam.ai` at the version you install.

---

## How to use this document

Steps are numbered and **strictly ordered**. Each has a duration, a goal, and an
acceptance test — don't move on until the acceptance test passes.

There are three **checkpoints**. At each one you either continue or trigger the
cut list. Checkpoints exist because a solo weekend has no slack: if you're behind
at checkpoint 2, you cannot make it up, and pretending otherwise is how you end
up Sunday night with a half-wired frontend and no working demo.

### Solo working rules

1. **Timebox hard.** If a step runs 50% over, stop and use the workaround in its
   "if stuck" note. Nothing here is worth losing the weekend to.
2. **Never refactor.** This is a prototype. Hardcode things. You'll rewrite it if
   it proves useful.
3. **One terminal, one browser tab.** Resist adding tooling, tests, Docker, or a
   framework. Every one of those is a two-hour detour.
4. **Test by talking to it.** You are the trainee. Do a real mock call after every
   major step.

---

## Scope

### In
- One hardcoded customer persona
- Advisor speaks → customer responds in voice, in character
- Customer reveals information only when probed
- **Advisor ends the call manually**; 5-minute hard cap as a backstop
- Transcript saved to disk, with the goal checklist attached for trainer review
- Cost summary shown when the call ends
- One session at a time

### Out
| Deferred | Why |
|---|---|
| **Automatic goal detection / auto-end** | **V2 — advisor clicks End for now** |
| Scoring / rubric | Simulation only for V1 |
| Barge-in / interruptions | Turn-taking complexity, no training value yet |
| Multiple personas | Prove one works first |
| Login, database, concurrency | Internal, one machine, flat files |
| Reconnect / resume | Restart the call |
| Live cost meter | End-of-call summary only |

**Definition of done:** you sit at the laptop, click Start, have a spoken
conversation with a believable customer, click End, and see the transcript and
the cost.

---

# SATURDAY

## Step 1 — Accounts and keys
**20 min** · *Do this first — signup verification can stall.*

1. `dashboard.sarvam.ai` → create account → generate API subscription key.
   Confirm free credits show a balance before continuing.
2. `console.anthropic.com` → create API key.
3. Put both in a scratch file. You'll make the real `.env` in Step 4.

**Acceptance:** two keys in hand, Sarvam shows credit.

**If stuck:** if Sarvam verification is delayed, carry on to Step 2 — it needs no
key — and come back.

---

## Step 2 — Write the persona and goal checklist
**60 min** · *On paper. No code. Do this while your energy is highest.*

This feels like the skippable step. It's the opposite: a working pipeline with a
flat persona is a worthless product, and a scrappy pipeline with a sharp persona
is useful on day one.

Create `personas/ramesh_v1.json`:

```json
{
  "id": "ramesh_v1",
  "name": "Ramesh Kulkarni",
  "age": 34,
  "city": "Pune",
  "occupation": "IT services, mid-level",
  "voice_id": "rahul",
  "surface_concern": "wants to save tax before March",
  "hidden_facts": {
    "monthly_income": "₹95,000",
    "home_loan_emi": "₹38,000/month, 18 years remaining",
    "spouse_working": false,
    "dependents": "wife, daughter aged 3, father aged 68",
    "existing_cover": "employer group policy only, ₹10 lakh",
    "health": "mild hypertension, on medication two years",
    "risk_appetite": "conservative, distrusts market-linked products",
    "horizon": "hasn't thought about it"
  },
  "objections": [
    "Isn't LIC enough? My father always said LIC only.",
    "This premium sounds too high with my EMI running.",
    "Let me discuss with my wife and call you back."
  ],
  "behaviour": "polite, slightly distracted, short answers unless probed",
  "goal_checklist": [
    "dependents", "monthly_income", "existing_cover", "loan_liability",
    "health_status", "risk_appetite", "investment_horizon"
  ]
}
```

**On the checklist in V1:** nothing consumes it automatically — that's V2. Write it
anyway. It's what makes the hidden facts coherent, and it gets **attached to the
saved transcript** (Step 10) so the trainer can tick items by eye during review.
Zero code, most of the value.

**Rules while writing it:**
- The **surface concern** must be shallow and slightly wrong, so the advisor has
  to dig past it.
- Every **hidden fact** must be something a competent advisor would surface with a
  specific question. If nothing would reveal it, delete it.
- Include at least one fact that **changes the right recommendation** — here, the
  home loan and the dependent father. This is where the training value lives.
- **Objections** should be things your trainers have actually heard.
- **Checklist items** must be objectively checkable from a transcript. "Asked
  about existing cover" is checkable; "built rapport" is not. Keep it to 6–8.

Also draft, in plain English, the behavioural rules you'll turn into a prompt in
Step 6. Ten bullets is enough.

**Acceptance:** the JSON exists and you can name the one fact that, if missed,
makes the advisor's recommendation wrong.

---

## Step 3 — Accent and vocabulary check
**45 min** · *Validates the vendor before you build a weekend on it.*

1. Write one paragraph loaded with the terms that break STT:
   *sum assured, ULIP, rider, premium paying term, endowment, ₹12 lakh, 1.2 crore,
   nominee, maturity benefit, lapse, IRDAI, ₹38,000 EMI, 15-year term.*
2. Record yourself and, if anyone's around, one or two colleagues reading it. Real
   accents, not a careful studio voice.
3. Run the files through Sarvam's **batch** STT endpoint — cheaper, same model, and
   you don't need the pipeline yet.
4. Score **only** the numbers and the jargon. General word error rate is irrelevant.
5. Write every miss into a list. It becomes the STT `prompt` field in Step 5.

Keep these recordings. They're your regression corpus when you change anything.

**Acceptance:** you know which terms Sarvam gets wrong, and you have a prompt
string to correct them.

**If stuck:** if the batch and streaming endpoints differ confusingly, move to
Step 4 and do this through the live pipeline later. Don't skip it entirely — this
45 minutes is the highest-leverage QA in the build.

---

## Step 4 — Environment and the dependency trap
**30 min**

```bash
mkdir mockcall && cd mockcall
python -m venv .venv && source .venv/bin/activate
pip install "pipecat-ai[sarvam,anthropic,webrtc]" python-dotenv
```

`.env`:
```
SARVAM_API_KEY=...
ANTHROPIC_API_KEY=...
```

**Check the known dependency issue immediately.** There's a reported problem where
`pipecat-ai[sarvam]` pins an outdated `sarvamai` package lacking the `saaras:v3`
mode parameter:

```bash
pip show sarvamai
pip index versions sarvamai
pip install --upgrade sarvamai   # if behind
python -c "from pipecat.services.sarvam.stt import SarvamSTTService; print('ok')"
```

**Do this now, not at hour six** when you're staring at a silent STT failure with
no obvious cause.

**Acceptance:** the import prints `ok`.

---

## Step 5 — Baseline pipeline
**90 min** · *Audio in, audio out. Nothing else.*

1. **Run Pipecat's own Sarvam example unmodified first.** Don't customise anything
   until you've heard a bot voice answer you.
   ```bash
   git clone https://github.com/pipecat-ai/pipecat-examples.git
   ```
   Search `examples/foundational/` for `sarvam`. Run it with your keys.

2. Only then write your own `bot.py`:

```python
import os
from dotenv import load_dotenv
from pipecat.pipeline.pipeline import Pipeline
from pipecat.services.sarvam.stt import SarvamSTTService
from pipecat.services.sarvam.tts import SarvamTTSService
from pipecat.services.anthropic.llm import AnthropicLLMService
from pipecat.transcriptions.language import Language

load_dotenv()

stt = SarvamSTTService(
    api_key=os.getenv("SARVAM_API_KEY"),
    model="saaras:v3",
    params=SarvamSTTService.InputParams(
        prompt=(
            "Indian insurance advisor speaking English. Expect terms like "
            "sum assured, ULIP, rider, premium paying term, endowment, "
            "term plan, lakh, crore, LIC, IRDAI, nominee, maturity benefit."
        ),
    ),
)

tts = SarvamTTSService(
    api_key=os.getenv("SARVAM_API_KEY"),
    model="bulbul:v3",
    voice_id="rahul",
    params=SarvamTTSService.InputParams(language=Language.EN, pace=1.0),
)

llm = AnthropicLLMService(
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    model="claude-haiku-4-5-20251001",
)

pipeline = Pipeline([
    transport.input(), stt, context_aggregator.user(),
    llm, tts, transport.output(), context_aggregator.assistant(),
])
```

Feed the STT `prompt` field from your Step 3 miss list. Cheapest accuracy win
available, and it directly fixes the numbers-and-jargon problem.

Use a local transport. **Do not touch telephony.**

**Acceptance:** you speak into your laptop mic and a voice answers. Content
doesn't matter yet.

**If stuck (>2h):** fall back to `SarvamHttpTTSService` instead of the WebSocket
service. Slower, simpler, gets you moving.

---

## Step 6 — Persona layer
**90 min**

Replace the generic assistant with the customer.

Write `render_system_prompt(persona) -> str`. The non-negotiable rules:

- You are this person. You are **not** an assistant and not helpful.
- Volunteer nothing beyond your surface concern.
- Reveal a hidden fact **only** when asked a question that would surface it in a
  real conversation. If asked nothing, say nothing.
- You have **no product knowledge**. If the advisor explains a product, react as a
  layperson — confusion, price sensitivity, a naive question. Never confirm or
  correct technical details.
- Reply in **2–3 sentences maximum**.
- Irrelevant question → mild confusion, steer back to your own concern.
- Advice that ignores what you've said → push back as a layperson would.
- Advisor silent or rambling → "Hello? Are you there?"
- **If the advisor wraps up, close warmly and in character** ("Okay, thank you,
  please send me the details"). Then stop talking. The session itself ends when
  the advisor clicks End — don't try to end it yourself.

Enable **prompt caching** on the persona block. It's re-sent every turn and cache
hits cost a tenth of base input.

**Acceptance:** a 3-minute conversation where it behaves like a customer, not a
chatbot, and does **not** hand you the hidden facts unprompted.

---

## Step 7 — Prompt iteration, round one
**90 min** · *This is the real work. It's writing, not coding.*

Do four or five mock calls and fix what breaks.

| Symptom | Fix |
|---|---|
| Volunteers hidden facts unprompted | Strengthen "reveal only when asked"; add a negative example |
| Sounds like an assistant ("Great question!") | Add "you are not helpful, you are a busy person"; forbid affirming phrases |
| Replies too long | Hard-cap sentences; add a `max_tokens` ceiling |
| Knows too much about products | Reinforce the layperson rule |
| Too easy — accepts anything | Add "sceptical and cost-conscious"; deploy objections harder |
| Keeps talking after the advisor wraps up | Reinforce the closing rule; add "then stop" |

---

## ✅ CHECKPOINT 1 — end of Saturday

**You should have:** a terminal-based mock call that feels like a real customer.

**If you have it:** you're on track. Sunday is plumbing and polish, and it's a
lighter day than Saturday.

**If you don't:** stop adding features. Spend Sunday morning finishing Steps 6–7
and ship a **terminal-only demo**. A convincing conversation with no UI is a far
better outcome than a pretty UI wrapped around a flat chatbot.

---

# SUNDAY

## Step 8 — Define the event contract
**30 min** · *Before you touch the frontend.*

You now know what the backend actually produces, so this will be accurate.

```jsonc
// server → client
{ "type": "session_started",   "persona_name": "Ramesh Kulkarni" }
{ "type": "user_transcript",   "text": "...", "final": true }
{ "type": "bot_transcript",    "text": "..." }
{ "type": "audio_chunk",       "data": "<base64 pcm>" }
{ "type": "session_ended",
  "reason": "ended_by_advisor",        // or "time_cap"
  "transcript_path": "transcripts/2026-08-08-1430.json",
  "usage_summary": {
    "turns": 12, "elapsed_seconds": 296,
    "stt_seconds": 154.0, "tts_chars": 2980,
    "llm_input_fresh_tokens": 2100, "llm_input_cached_tokens": 21400,
    "llm_output_tokens": 1050,
    "cost_inr": { "stt": 3.85, "tts": 8.94, "llm": 2.40, "total": 15.19 }
  }
}
{ "type": "error", "message": "..." }

// client → server
{ "type": "start_session", "persona_id": "ramesh_v1" }
{ "type": "audio_chunk",   "data": "<base64 pcm>" }
{ "type": "end_session" }
```

No `goal_progress` message in V1 — nothing is tracking coverage. Add it in V2.

Write this into `contract.md`. Working solo you won't forget it, but you *will*
change your mind halfway through the frontend if it isn't written down.

---

## Step 9 — Usage accumulator
**60 min** · *Backend only. Nothing on screen yet.*

Counters increment as the call runs; totals compute once at the end. Because
nothing is emitted mid-call, this cannot affect the audio path at all.

**Rate config — `rates.json`, never hardcoded:**
```json
{
  "currency": "INR",
  "usd_to_inr": 88.0,
  "stt":  { "unit": "per_minute",    "rate": 1.50, "model": "saaras:v3" },
  "tts":  { "unit": "per_10k_chars", "rate": 30.00, "model": "bulbul:v3" },
  "llm":  { "unit": "per_mtok_usd",  "model": "claude-haiku-4-5-20251001",
            "input": 1.00, "output": 5.00, "cache_read": 0.10 },
  "verified_on": "2026-08-08",
  "source": ["sarvam.ai/api-pricing", "anthropic.com/pricing"]
}
```
Rates move. A `verified_on` date makes the number auditable rather than folklore.

**Where each number comes from:**

| Metric | Source |
|---|---|
| `stt_seconds` | Mic-button hold time. Measure on the **client** — more accurate than server-side timing. |
| `tts_chars` | `len()` of the text you hand to TTS, counted before synthesis. |
| `llm_*_tokens` | The Anthropic response `usage` block. **Never estimate with a tokenizer** — the API tells you exactly. |

**Formula:**
```
stt_inr = (stt_seconds / 60) * 1.50
tts_inr = (tts_chars / 10000) * 30.00
llm_usd = fresh_input/1e6*1.00 + cached_input/1e6*0.10 + output/1e6*5.00
llm_inr = llm_usd * 88.0
```

**Count fresh and cached input separately.** Lump them and the LLM reads ~8–10×
too expensive, and you'll wrongly conclude the LLM is your cost driver. It isn't
— TTS is.

Also append a per-turn row to `usage/<timestamp>.csv` as the call runs. Costs
nothing, never reaches the frontend, and it's how you find which turns were
expensive.

**Acceptance:** printed totals after a terminal call look plausible.

---

## Step 10 — Session end and persistence
**45 min**

**Two ways a call ends:**
1. **Advisor clicks End** — the normal path. Emits `session_ended` with reason
   `ended_by_advisor`.
2. **5-minute cap** — a server-side timer fires, reason `time_cap`. This is a
   backstop against a forgotten open session, not a training device.

Put the cap in config (`MAX_CALL_SECONDS = 300`), not inline. You will want to
change it — see the note in the Reference section.

**On either path,** write `transcripts/<timestamp>.json` containing:
- full turn-by-turn transcript with speaker labels and timestamps
- the persona id and its `goal_checklist`
- the usage summary
- the end reason

Attaching the checklist is what makes the transcript useful to a trainer: they
read the conversation with the list of things the advisor should have surfaced
sitting right next to it, and tick them by eye. That's your review workflow for
V1 — no code, and it's the manual version of what V2 automates.

**Acceptance:** after a call, the file exists, is readable, and contains the
checklist.

---

## ✅ CHECKPOINT 2 — Sunday midday

**You should have:** a full call loop working headless — persona, manual end,
5-minute cap, transcript on disk with checklist, cost totals printed.

**If you're behind:** skip Step 12 (cost summary card) and go straight to the
frontend. A demo you can drive from a browser beats a nicer end screen.

---

## Step 11 — Browser frontend
**150 min** · *Deliberately ugly. One HTML file, vanilla JS. No framework.*

**Layout:** header (persona name, call timer) · transcript pane (scrolling) ·
control bar (Start / mic / **End Call**).

The End button is now load-bearing, so make it obvious and give it a confirm step
— an accidental click mid-call loses the exercise.

Show the call timer counting **down** from 5:00 so the advisor can pace
themselves, with a colour change in the last 60 seconds.

**Mic capture:** `getUserMedia` → PCM → WebSocket per the contract. Play returned
audio through Web Audio API.

**Use push-to-talk.** The advisor holds the mic button or spacebar while speaking
and releases when done. This removes end-of-speech detection entirely — normally
500–700ms of your latency budget and the fiddliest thing to tune. Pipecat's Sarvam
TTS supports interruption natively, so barge-in is available later; leave it
**off** for V1.

**Transcript pane:** render `user_transcript` and `bot_transcript` as a chat log,
colour-coded by speaker. Make it copyable.

**Acceptance:** you can run a complete call from the browser and end it cleanly.

**If stuck (>3h):** stop. Demo from the terminal. This is the largest single step
and the most likely to eat the day.

---

## Step 12 — Cost summary card
**45 min**

One card on `session_ended`, next to the transcript link.

```
Call complete · 4:56 · 12 turns · ended by advisor

  Speech-to-text      154 s          ₹3.85
  Text-to-speech      2,980 chars    ₹8.94
  LLM input (fresh)   2,100 tok      ₹0.18
  LLM input (cached)  21,400 tok     ₹0.19
  LLM output          1,050 tok      ₹2.03
  ─────────────────────────────────────────
  Total                              ₹15.19

  Cache hit rate 91%  ·  ₹1.27 per turn        [Copy]
```

Two derived figures earn their place: **cache hit rate** (tells you instantly
whether prompt caching works) and **cost per turn** (the number that scales). The
Copy button matters — you'll paste this into a budget conversation.

---

## Step 13 — Failure handling
**45 min** · *Deliberately minimal.*

| Failure | Handling |
|---|---|
| Empty / garbage transcript | Customer says "Sorry, I couldn't hear you, can you repeat?" — free realism |
| LLM or TTS timeout > 4s | Same line, played from a **pre-generated WAV** so it works even when TTS is what died |
| Any API error | Retry once with 500ms backoff, then fall through to the above |
| Anything worse | Error banner + "Restart call" button |

**Pre-generate the fallback WAV now** and commit it. It's the one failure path that
has to work when the vendor is down.

**Do not build:** fallback vendors, session resume, reconnect logic. None of it
teaches anyone to sell insurance.

---

## Step 14 — Prompt iteration, round two
**60 min**

Three more full calls through the browser. Fix persona problems only — no code
changes. Use the Step 7 symptom table.

Pay attention to whether 5 minutes is actually enough to surface the checklist. If
you're consistently getting cut off mid-discovery, that's a signal about the cap,
not about the advisor.

If you can grab a senior advisor for ten minutes, sit them in front of it and ask
one question: *"Would a new joiner learn anything from that?"* Their objections
are worth more than your own.

---

## Step 15 — Validate the cost figures
**20 min** · *Last thing. Don't skip.*

Compare your reported totals against the Sarvam dashboard and the Anthropic
console for the same period. They should agree within a few percent.

**A confidently wrong cost figure is worse than none** — someone will budget off it.

---

## ✅ CHECKPOINT 3 — Sunday evening

Tick all of these:

- [ ] Start a call from the browser without help
- [ ] Customer's first line is in character and unprompted
- [ ] Customer does not reveal the home loan until asked about liabilities
- [ ] Customer closes warmly when you wrap up, and stops talking
- [ ] End Call works and produces a transcript
- [ ] 5-minute cap fires cleanly if you let it run
- [ ] Turn latency stays under 2 seconds across the call
- [ ] "₹12 lakh" and "sum assured" transcribe correctly
- [ ] Transcript on disk, readable, with the checklist attached
- [ ] Cost breakdown appears when the call ends
- [ ] Cost figure validated against both vendor dashboards

---

# Reference

## A note on the 5-minute cap

Five minutes is tight for a discovery conversation covering seven checklist items
— that's roughly 40 seconds per item including the customer's answers, with no
room for rapport or objection handling. Expect trainees to get cut off mid-flow at
first.

That may be exactly what you want (short, focused drills that force efficient
probing), or it may frustrate people. Because it's a single config value, you'll
know after three or four real calls in Step 14. If calls are consistently ending
at the cap rather than at a natural close, raise it to 10 minutes.

Note the cost figures below assume the 5-minute cap; they roughly double at 10.

## Latency budget (key release → first sound)

| Stage | Target |
|---|---|
| Final transcript | 150–300 ms |
| LLM first token | 300–600 ms |
| TTS first audio | 150–400 ms |
| Network + buffer | ~100 ms |
| **Total** | **0.8–1.4 s** (tolerance: 2.0 s) |

**If over budget, in this order:**
1. Lower TTS `min_buffer_size` from its default of 50 toward ~25. Lower values
   reduce latency but can affect prosody. **This is your main dial.**
2. Confirm TTS is sentence-chunked — start playing sentence one while the rest
   generates. Without this, one long reply blows the budget.
3. Shorten customer replies in the prompt (2 sentences, not 3).
4. Confirm STT streams during speech rather than transcribing on release.
5. Only then consider swapping vendors.

## Expected cost

Per **5-minute** session:

| Component | Usage | Cost |
|---|---|---|
| STT (₹1.5/min streamed) | ~2.5–3.5 min held mic | ₹4–6 |
| TTS (₹30/10k chars) | ~3,000 chars | ₹9 |
| LLM (Haiku 4.5, cached, single call per turn) | ~24k in / 1k out | ₹2–3 |
| **Total** | | **₹15–20** |

Dropping the goal-detection call removed a second LLM request per turn, so LLM
cost is lower than earlier estimates. TTS is now clearly your largest line item.

At 10 trainees × 2 sessions/day × 20 days ≈ 440 sessions → roughly
**₹7,000–9,000/month**. Double it if you raise the cap to 10 minutes. The build
weekend itself is covered by signup credits.

**Read the summary for three signals:**
1. **Cache hit rate below ~80%** → caching isn't working. Static content must come
   first in the prompt.
2. **TTS chars above ~3,500 for a 5-minute call** → customer talking too much.
   Tighten the sentence rule. Fixes cost, realism, and latency at once.
3. **STT seconds ≫ half of call duration** → mic held during silence. A UI cue,
   not a code fix.

## Gotchas

1. **`sarvamai` version pin** — the Pipecat extra may install an outdated version
   lacking `saaras:v3` parameters. Checked in Step 4. (Pipecat issue #3783.)
2. **Numbers are your highest-cost STT error.** "₹12 lakh" heard as "₹12,000"
   silently corrupts the exercise. The STT `prompt` field and Step 3 exist for this.
3. **Use STT finals only for the LLM.** Partials are for the on-screen transcript.
4. **Cache the persona block** or you re-pay full input price every turn.
5. **Pre-generate the fallback WAV.** A TTS failure can't be announced by TTS.
6. **Voice ID belongs in the persona file**, not the code.
7. **Bulbul v3 has a different speaker list from v2.** Voice IDs may not carry over.
8. **Cached vs. fresh input tokens are billed ~10× apart.** Don't lump them.
9. **Read token counts from the API `usage` block**, never estimate.
10. **Keep the accumulator out of the audio path.**
11. **Confirm the End button.** It's the only way a call finishes normally now; an
    accidental click loses the exercise.

## Master cut list

When you fall behind, cut in this order:

1. Cost summary card (the CSV still has the numbers)
2. Countdown timer (a plain elapsed clock is fine)
3. Failure handling
4. Transcript pane (read the JSON directly)
5. Browser frontend entirely — demo from the terminal

**Never cut Steps 2, 6, or 7.** The persona quality *is* the product.

## V2 backlog

Ordered by likely value:

1. **Automatic goal detection and auto-end** — a concurrent Haiku call after each
   advisor turn returning which checklist items are covered; close the call
   naturally when all are ticked. Adds a `goal_progress` event. This is the
   deferred V1 feature and the most obvious next thing.
2. **Persona library** — 5–8 archetypes (young single, family breadwinner,
   near-retirement, HNI, sceptic)
3. **Post-call feedback** — one LLM pass over the finished transcript returning
   what was missed. Zero latency cost, high perceived value.
4. **Off-track flagging** — same pass, flags irrelevant or non-compliant turns
5. **Trainer dashboard** — session list, filter by trainee, open transcript
6. **Multi-user concurrency** — the service is already mostly stateless
7. **Barge-in** — already supported by the TTS service, just enable it
8. **Hinglish support** — Sarvam handles code-mixing natively; a prompt change
   plus a new test corpus
9. **Scoring rubric** — only once trainers agree what "good" looks like
