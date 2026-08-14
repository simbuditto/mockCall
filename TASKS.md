# Automation tasks — feature/automation

This file is the spec for an autonomous Claude Code run. Work through the tasks
**in order**. After each task, run `bash scripts/verify.sh`; do not move on until
it passes. Commit after each green task with a clear message. Do not finish until
every task is done and `scripts/verify.sh` exits 0.

## Operating rules
- Never touch `.env`, and never hardcode API keys. Keep everything config-driven.
- Personas are data (`personas/*.json`) rendered by `persona.py` — do not hardcode
  persona content in code.
- Keep `index.html` a single self-contained file (vanilla JS, no build step).
- The **element IDs in the acceptance criteria are a contract** — use them exactly,
  because `scripts/verify.sh` greps for them.
- Some acceptance is UX and cannot be auto-tested; those are marked **[manual QA]**
  and listed in `QA_CHECKLIST.md` (create it) for a human to tick after the run.

---

## Task 1 — Choose the microphone *before* the session starts

Today the mic can be picked from a bar during the call. Change the flow so mic
selection and an explicit **confirmation** happen on a pre-session screen; the
session cannot begin until the user has confirmed a device.

**Implement**
- A pre-session "device setup" step shown before the call UI, containing the mic
  dropdown (`id="micSelect"`, already exists) and a confirm control
  **`id="mic-confirm"`**.
- The **Start Call** control stays disabled until the mic is confirmed.
- Only the confirmed device's audio is used for the session (keep `updateMic`).

**Acceptance**
- `index.html` contains `id="mic-confirm"`. *(auto)*
- **[manual QA]** On load you pick a mic and click confirm before any call can start;
  the confirmed device is the one transmitted.

---

## Task 2 — Five customer profiles chosen on a landing page

Replace the single hardcoded persona with a landing page offering **five distinct
profiles**; the user picks one, and that persona drives the session.

**Implement**
- Author **five** persona files in `personas/` following the exact structure of
  `personas/ramesh_v1.json` (keys: `id, name, age, city, occupation, voice_id,
  surface_concern, hidden_facts, objections, behaviour, goal_checklist`). Use
  `personas/ramesh_v1_behaviour.md` as the quality reference. Suggested archetypes:
  young single earner, family breadwinner (the existing Ramesh), near-retirement,
  high-net-worth individual, and a hardened sceptic. Give each a distinct
  `voice_id` from Bulbul v3's speaker list.
- A landing screen with a profile chooser **`id="profile-select"`** listing the five
  profiles (name + one-line summary). Selecting one carries its `persona_id`
  forward into the session.
- Pass the chosen `persona_id` from the browser to `bot.py` so the right persona
  loads. Research the simplest reliable Pipecat mechanism (e.g. a query param on
  the `webrtcUrl`/offer endpoint that `bot.py` reads, or `sendClientMessage`
  before the pipeline builds). **Fallback if dynamic selection proves hard:** run
  one bot per persona on its own port and map each profile to a port in the
  frontend; document whichever approach you choose in `contract.md`.

**Acceptance**
- `personas/` holds **≥5** valid persona files, each with all required keys, and
  `persona.py` renders each without error. *(auto)*
- `index.html` contains `id="profile-select"`. *(auto)*
- **[manual QA]** The landing page shows five profiles; picking one starts a call
  where that customer's greeting and behaviour match the chosen profile.

---

## Task 3 — Show session usage/stats only on request

The cost/stats card currently appears automatically when a call ends. Make it
appear only when the user asks for it.

**Implement**
- On call end, do **not** render the cost card automatically. Instead show a
  control **`id="show-stats"`** ("Show session stats"). Clicking it renders the
  existing cost card (reuse `renderCostCard`).

**Acceptance**
- `index.html` contains `id="show-stats"`, and the cost card is not appended on
  the disconnect path without a click. *(auto — verify greps that `renderCostCard`
  is called from the `show-stats` handler, not directly from `endedUI`.)*
- **[manual QA]** After a call, no stats show until you click "Show session stats".

---

## Finishing
- Ensure `bash scripts/verify.sh` exits 0.
- Update `README.md` (profiles, new flow) and `contract.md` (persona selection).
- Fill in `QA_CHECKLIST.md` with the **[manual QA]** items above.
- Open a pull request into `main` summarising the changes and the verify output.
