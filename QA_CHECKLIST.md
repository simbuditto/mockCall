# Manual QA checklist

Automated coverage (`bash scripts/verify.sh`) enforces the code contract:
Python parses, JSON is valid, five personas render, the frontend module parses,
the cost accountant runs, and the element-ID contract holds. The items below
are the UX checks a human still needs to tick after the automated run.

Prereqs: keys in `.env`, venv active, `python bot.py` running on :7860,
`python -m http.server 8000` serving the repo root. Open
`http://localhost:8000/` in Chrome/Edge/Safari.

## Task 1 — Pre-session mic confirmation

- [ ] On first load, the landing screen appears; the call footer is hidden.
- [ ] After picking a profile, the **device setup** card is shown with the
      mic dropdown and a **Confirm microphone** button.
- [ ] The confirm button is disabled until at least one mic is enumerated.
- [ ] Clicking **Confirm microphone** advances to the call view; **Start Call**
      is now enabled.
- [ ] If the mic dropdown is changed on the setup screen after confirming,
      re-confirmation is required before Start Call unlocks.
- [ ] During the call, the *confirmed* microphone is the one Sarvam transcribes
      (swap headsets and check the transcript follows the confirmed device).

## Task 2 — Five customer profiles

- [ ] The landing page shows exactly five profile cards (Priya, Ramesh, Vikram,
      Krishnamurthy, Suresh) with a short one-line summary each.
- [ ] Selecting a card highlights it and carries the `persona_id` forward.
- [ ] The customer's greeting and behaviour on the call match the chosen
      profile (voice, opening concern, and objections all differ from Ramesh).
- [ ] Refreshing and picking a different profile yields a visibly different
      customer on the next call — no persona bleed-through.

## Task 3 — Stats only on request

- [ ] After ending a call, **no** cost card appears automatically — the
      transcript stays as-is with a small **Show session stats** button.
- [ ] Clicking **Show session stats** loads and renders the cost card exactly
      once, and the button disappears.
- [ ] Starting a fresh call clears any cost card left over from the previous
      session before the new transcript begins.
