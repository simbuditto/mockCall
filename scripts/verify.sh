#!/usr/bin/env bash
# Automated "definition of done" for feature/automation.
# Deliberately dependency-light: parses code, validates JSON, renders personas,
# syntax-checks the frontend JS, and enforces the element-ID contract. Needs only
# python3 and node — no Pipecat install, no API keys.
set -uo pipefail
cd "$(dirname "$0")/.."

fail=0
pass() { echo "  ✓ $1"; }
err()  { echo "  ✗ $1"; fail=1; }

echo "[1/6] Python parses (py_compile)"
if python3 -m py_compile bot.py persona.py usage.py persistence.py generate_fallback.py \
      stt_test/run_stt_check.py 2>/tmp/pyc.log; then
  pass "all .py files parse"
else
  err "py_compile failed:"; cat /tmp/pyc.log
fi

echo "[2/6] JSON is valid"
if python3 - <<'PY' 2>/tmp/json.log; then pass "rates.json + personas valid JSON"; else err "invalid JSON:"; cat /tmp/json.log; fi
import json, glob
json.load(open("rates.json"))
for f in glob.glob("personas/*.json"):
    json.load(open(f))
PY

echo "[3/6] At least 5 personas, complete, renderable, valid Bulbul v3 voice"
if python3 - <<'PY' 2>/tmp/persona.log; then pass "5+ personas render, voices valid"; else err "persona check failed:"; cat /tmp/persona.log; fi
import glob, json, sys
import persona
REQ = {"id","name","age","city","occupation","voice_id","surface_concern",
       "hidden_facts","objections","behaviour","goal_checklist"}
# Valid speakers for bulbul:v3 (pipecat SarvamTTSSpeakerV3).
V3 = {"aditya","ritu","priya","neha","rahul","pooja","rohan","simran","kavya",
      "amit","dev","ishita","shreya","ratan","varun","manan","sumit","roopa",
      "kabir","aayan","shubh","ashutosh","advait","amelia","sophia"}
files = glob.glob("personas/*.json")
assert len(files) >= 5, f"need >=5 personas, found {len(files)}"
for f in files:
    p = json.load(open(f))
    missing = REQ - set(p)
    assert not missing, f"{f} missing keys: {missing}"
    assert p["voice_id"] in V3, f"{f}: voice_id {p['voice_id']!r} is not a valid bulbul:v3 speaker"
    assert persona.render_system_prompt(p), f"{f} rendered empty"
print(f"ok: {len(files)} personas")
PY

echo "[4/6] Frontend JS syntax"
if python3 - <<'PY' 2>/dev/null; then
import re
html = open("index.html", encoding="utf-8").read()
m = re.search(r'<script type="module">(.*?)</script>', html, re.S)
open("/tmp/ui.mjs","w").write(m.group(1) if m else "SYNTAX ERROR no module")
PY
  if node --check /tmp/ui.mjs 2>/tmp/node.log; then pass "index.html module parses"; else err "JS syntax error:"; cat /tmp/node.log; fi
else
  err "could not extract <script type=module> from index.html"
fi

echo "[5/6] Cost accountant self-test"
if python3 usage.py >/tmp/usage.log 2>&1 && grep -q "cost_inr" /tmp/usage.log; then
  pass "usage.py cost math runs"
else
  err "usage.py self-test failed:"; cat /tmp/usage.log
fi

echo "[6/6] Frontend element-ID contract (TASKS.md)"
for id in "mic-confirm" "profile-select" "show-stats"; do
  if grep -q "id=\"$id\"" index.html; then pass "id=$id present"; else err "index.html missing id=\"$id\""; fi
done

echo
if [ "$fail" -eq 0 ]; then echo "VERIFY: PASS"; else echo "VERIFY: FAIL"; fi
exit $fail
