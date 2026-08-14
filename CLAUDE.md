# CLAUDE.md — context for autonomous work

Mock-call voice trainer: a browser talks to an AI insurance **customer** (persona),
advisor practises, transcript + cost saved. Read `README.md` for the full picture
and `TASKS.md` for the current work.

## How to work here
- The current job is `TASKS.md`. Do tasks in order; after each, run
  `bash scripts/verify.sh` and do not proceed until it exits 0. Commit per task.
- **Never** read, edit, print, or commit `.env`. Never hardcode API keys.
- Keep `index.html` a single self-contained file (vanilla JS, ESM from CDN, no build).
- Personas are data in `personas/*.json`, rendered by `persona.py`. Add profiles as
  files, never as hardcoded strings.
- Element IDs named in `TASKS.md` are a contract — `scripts/verify.sh` greps for them.
- Config over hardcoding: call cap, voice, rates, persona path are settings.

## Key files
- `bot.py` — Pipecat pipeline (STT→LLM→TTS), session lifecycle, 5-min cap
- `persona.py` — persona JSON → system prompt
- `usage.py` — cost accountant + observers (guarded pipecat import → runs without it)
- `persistence.py` — writes transcript + checklist + usage JSON on call end
- `index.html` — the whole frontend
- `rates.json` — auditable pricing; `contract.md` — client⇄server events

## Running (for manual QA, needs keys + venv)
```
python bot.py                 # terminal 1 (bot on :7860)
python -m http.server 8000    # terminal 2, open http://localhost:8000/
```

## Definition of done
`bash scripts/verify.sh` exits 0, README + contract updated, `QA_CHECKLIST.md`
lists the manual UX checks, and a PR into `main` is opened.
