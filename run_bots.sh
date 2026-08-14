#!/usr/bin/env bash
# Launch one bot per persona, each on its own port. The frontend (profiles.json)
# routes the chosen customer to the matching port. Ctrl+C stops all of them.
#
# Usage:  source .venv/bin/activate && ./run_bots.sh
# Then serve the frontend in another terminal:  python -m http.server 8000
set -euo pipefail
cd "$(dirname "$0")"

# id:port must match profiles.json
declare -a BOTS=(
  "personas/ramesh_v1.json:7860"
  "personas/priya_v1.json:7861"
  "personas/vikram_v1.json:7862"
  "personas/krishnamurthy_v1.json:7863"
  "personas/suresh_v1.json:7864"
)

trap 'echo; echo "Stopping all bots…"; kill 0' EXIT INT TERM

for entry in "${BOTS[@]}"; do
  persona="${entry%%:*}"
  port="${entry##*:}"
  echo "Starting $(basename "$persona" .json) on :$port"
  PERSONA_PATH="$persona" python bot.py --port "$port" &
  sleep 1   # stagger startup so the prebuilt UI assets don't race
done

echo
echo "All five bots starting. Serve the frontend:  python -m http.server 8000"
echo "Then open http://localhost:8000/  ·  Ctrl+C here stops every bot."
wait
