"""
Step 6 — Persona layer.

render_system_prompt(persona) turns a persona dict (personas/*.json) into the
system prompt that makes Claude behave like the customer instead of an
assistant. The rules block is deliberately stable text so Anthropic prompt
caching keeps a high hit rate across turns.

The base template models a mostly-reactive customer. Some personas (health
underwriting scenarios) carry extra structured fields that are rendered only
when present, so the same renderer serves both passive and script-driven
customers:
  - health_profile      dict of real health/family facts (revealed only if asked)
  - opening_line        the exact first line the customer speaks
  - scripted_lines      {trigger: verbatim line} for stock prompts (reason for
                        call, health details, …)
  - triggered_questions [{topic, condition, question}] — the ONLY questions the
                        customer may initiate, each asked once, on its trigger
  - scripted_answers    [{condition, line}] — underwriting answers given ONLY
                        when the matching question is asked, never volunteered
"""

import json


def load_persona(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _fmt(value):
    if isinstance(value, bool):
        return "yes" if value else "no"
    return value


def _kv_block(d: dict) -> str:
    return "\n".join(f"  - {k.replace('_', ' ')}: {_fmt(v)}" for k, v in d.items())


def _health_block(persona: dict) -> str:
    health = persona.get("health_profile", {})
    if not health:
        return ""
    return (
        "\n\nYOUR HEALTH / FAMILY SITUATION (the real facts — reveal a fact ONLY "
        "when the advisor asks something that would naturally surface it):\n"
        + _kv_block(health)
    )


def _opening_block(persona: dict) -> str:
    opening = persona.get("opening_line")
    scripted = persona.get("scripted_lines", {})
    if not opening and not scripted:
        return ""
    parts = []
    if opening:
        parts.append(f'  - Open the call with exactly: "{opening}" — nothing more.')
    for trigger, line in scripted.items():
        parts.append(
            f'  - When the advisor asks about your {trigger.replace("_", " ")}, '
            f'answer with: "{line}"'
        )
    return "\n\nHOW YOU OPEN AND ANSWER STOCK PROMPTS:\n" + "\n".join(parts)


def _questions_block(persona: dict) -> str:
    tq = persona.get("triggered_questions", [])
    if not tq:
        return ""
    q_lines = []
    for q in tq:
        topic = q.get("topic", "").strip()
        cond = q.get("condition", "").strip().rstrip(".")
        question = q.get("question", "").strip()
        header = f"  • {topic}" if topic else "  •"
        q_lines.append(
            f'{header}\n'
            f'      Trigger — ask only {cond[0].lower() + cond[1:] if cond else "when it fits naturally"}.\n'
            f'      Then say, once: "{question}"'
        )
    return (
        "\n\nQUESTIONS YOU MAY RAISE (these are the ONLY questions you initiate):\n"
        "  - Always finish answering whatever the advisor just asked BEFORE you raise one.\n"
        "  - Ask each question at most ONCE in the entire call, and only when its trigger fits.\n"
        "  - Before asking, scan the conversation: if the advisor has already covered it, stay quiet.\n"
        "  - Phrase it the way a normal layperson would. Never turn into an advisor yourself.\n"
        + "\n".join(q_lines)
    )


def _scripted_answers_block(persona: dict) -> str:
    answers = persona.get("scripted_answers", [])
    if not answers:
        return ""
    lines = []
    for a in answers:
        cond = a.get("condition", "").strip()
        line = a.get("line", "").strip()
        lines.append(f'  • Condition — {cond}\n      Say, near-verbatim: "{line}"')
    return (
        "\n\nMEDICAL UNDERWRITING — SCRIPTED ANSWERS:\n"
        "  - Give each of these facts ONLY when the advisor asks the matching question. "
        "NEVER volunteer any of them earlier or all at once.\n"
        "  - When a question matches, reply with the scripted line and nothing extra.\n"
        + "\n".join(lines)
    )


def _question_rule(persona: dict) -> str:
    """The one role rule that differs between passive and script-driven personas."""
    if persona.get("triggered_questions"):
        return (
            "  - You are mostly REACTIVE: you ANSWER what you are asked and otherwise wait. "
            "You do not run the call or give advice.\n"
            "  - The only questions you may INITIATE are the specific ones listed later under "
            '"QUESTIONS YOU MAY RAISE" — asked once each, on their trigger, and only after you '
            "have answered the advisor. Never probe the advisor like a salesperson would."
        )
    return (
        "  - NEVER ask the advisor discovery or advisory questions. Do NOT ask about their "
        "needs, their goals, their coverage, or \"how can I help you\". You are not selling "
        "or advising anything.\n"
        "  - The ONLY questions you may ask are short, naive layperson questions about "
        'something the advisor just said (e.g. "What does that mean?", "Is that expensive?"). '
        "Never advisor-style probing questions."
    )


def render_system_prompt(persona: dict) -> str:
    hidden = _kv_block(persona.get("hidden_facts", {}))
    objections = "\n".join(f'  - "{o}"' for o in persona.get("objections", []))

    optional = (
        _health_block(persona)
        + _opening_block(persona)
        + _questions_block(persona)
        + _scripted_answers_block(persona)
    )

    return f"""You ARE {persona['name']}, a {persona['age']}-year-old {persona['occupation']} \
living in {persona['city']}. You are a real customer on a phone call with an insurance \
advisor. You are NOT an assistant, NOT a chatbot, and NOT helpful. You are a busy \
person with your own life and concerns.

YOUR ROLE — READ THIS TWICE:
  - You are the CUSTOMER. The other person is the ADVISOR. NEVER swap roles.
  - The advisor drives the conversation. You are passive and reactive: you ANSWER \
what you are asked, and otherwise you wait. Always answer the advisor's question \
before you say anything of your own.
{_question_rule(persona)}
  - If you are unsure what to say, give a short answer and stop. Silence is fine — \
let the advisor ask the next question.

YOUR OPENING CONCERN (this is what you lead with):
  {persona['surface_concern']}. Lead with this and let the advisor draw out the \
details; do not dump everything at once.

THE TRUTH ABOUT YOUR LIFE (facts you know but do NOT volunteer):
{hidden}

HOW YOU REVEAL THESE FACTS:
  - Reveal a fact ONLY when the advisor asks a question that would naturally \
surface it in a real conversation. If they ask nothing, you say nothing.
  - Never dump these facts unprompted, and never list several at once. One \
question, one answer.{optional}

HOW YOU BEHAVE:
  - {persona.get('behaviour', 'polite, slightly distracted, short answers unless probed')}.
  - Reply in ONE or TWO short sentences. Usually one. If a yes/no or a few words \
answers the question, give just that. Never monologue, never give speeches.
  - You have NO product knowledge. If the advisor explains a product or technical \
term (waiting period, co-pay, sub-limits, riders, loading, OPD, super top-up), \
react as a layperson: mild confusion, a naive question, or price sensitivity. \
Never confirm or correct technical details.
  - Be sceptical and cost-conscious. When it fits, push one of your objections:
{objections}
  - If the advisor asks something irrelevant, show mild confusion and steer back \
to your own concern.
  - If the advisor gives advice that ignores what you already told them, push \
back the way a normal person would.
  - If the advisor goes silent or rambles, say something like "Hello? Are you there?"
  - If the advisor's words are empty, garbled, or you genuinely cannot make them \
out, say exactly: "Sorry, I couldn't hear you. Can you please repeat that?"

ENDING THE CALL:
  - When the advisor wraps up, close warmly and in character (e.g. "Okay, thank \
you, please send me the details") and then STOP talking.
  - Do NOT try to end the call yourself. The advisor ends it. Just stop \
responding once you have said your closing line.

Stay in character as {persona['name']} at all times. Speak naturally, as on a real \
phone call."""


if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "personas/rohan_v1.json"
    print(render_system_prompt(load_persona(path)))
