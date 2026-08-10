"""
Step 10 — session persistence.

Writes one JSON file per call into transcripts/. The point of attaching the
goal_checklist is the V1 review workflow: a trainer reads the conversation with
the list of things the advisor should have surfaced sitting right next to it, and
ticks them by eye. That's the manual version of what V2 automates.
"""

import os
import json
import time


def save_session(persona, transcript, usage_summary, end_reason,
                 out_dir="transcripts", session_id=None):
    """Write transcripts/<session_id>.json and return its path.

    transcript: list of {"speaker", "text", "timestamp"} dicts.
    """
    session_id = session_id or time.strftime("%Y-%m-%d-%H%M%S")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{session_id}.json")

    data = {
        "session_id": session_id,
        "persona_id": persona.get("id"),
        "persona_name": persona.get("name"),
        "goal_checklist": persona.get("goal_checklist", []),
        "end_reason": end_reason,          # "ended_by_advisor" or "time_cap"
        "usage_summary": usage_summary,
        "transcript": transcript,
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # Stable pointer to the most recent session, fetched by the browser cost
    # card (V1 runs one session at a time, so a single latest.json is enough).
    with open(os.path.join(out_dir, "latest.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return path


if __name__ == "__main__":
    # Self-test with a tiny fake session.
    demo_persona = {
        "id": "ramesh_v1", "name": "Ramesh Kulkarni",
        "goal_checklist": ["dependents", "existing_cover", "loan_liability"],
    }
    demo_transcript = [
        {"speaker": "customer", "text": "Hello, I wanted to save some tax before March.",
         "timestamp": "2026-08-10T10:00:01Z"},
        {"speaker": "advisor", "text": "Sure. Do you have any loans running?",
         "timestamp": "2026-08-10T10:00:08Z"},
        {"speaker": "customer", "text": "Yes, a home loan, about 38,000 a month.",
         "timestamp": "2026-08-10T10:00:14Z"},
    ]
    demo_usage = {"turns": 2, "cost_inr": {"total": 1.20}}
    p = save_session(demo_persona, demo_transcript, demo_usage, "ended_by_advisor",
                     out_dir="transcripts", session_id="selftest")
    print("wrote", p)
    print(open(p, encoding="utf-8").read())
