#!/usr/bin/env bash
# HIVE MIND smoke test: health → create → build → simulate → report → chat.
set -euo pipefail
API="${API:-http://localhost:8000/api}"
GREEN='\033[0;32m'; NC='\033[0m'
ok(){ echo -e "${GREEN}✓ $1${NC}"; }

echo "== health =="
curl -fsS "$API/health" | tee /tmp/hm_health.json
grep -q '"ok":true' /tmp/hm_health.json && ok "health"

echo "== create project =="
PROJECT=$(curl -fsS -X POST "$API/projects" -H 'Content-Type: application/json' -d '{
  "name": "Smoke Test Swarm",
  "question": "How will public sentiment evolve over the next week?",
  "seedText": "A major technology company announced a new AI chip. Regulators in three countries opened antitrust reviews. Social media responded with a mix of excitement, skepticism and fear about job displacement. Analysts are divided on the near-term market impact."
}')
PID=$(echo "$PROJECT" | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
ok "project $PID"

echo "== build world =="
curl -fsS -X POST "$API/projects/$PID/build" -H 'Content-Type: application/json' -d '{"agentCount":40,"platformCount":2}' >/dev/null
ok "built"

echo "== simulate =="
RUN=$(curl -fsS -X POST "$API/projects/$PID/simulate" -H 'Content-Type: application/json' -d '{"rounds":6,"speed":50}')
RID=$(echo "$RUN" | python3 -c 'import sys,json;print(json.load(sys.stdin)["runId"])')
ok "run $RID"

for i in $(seq 1 60); do
  S=$(curl -fsS "$API/runs/$RID" | python3 -c 'import sys,json;print(json.load(sys.stdin)["status"])')
  [ "$S" = "complete" ] && break; sleep 1
done
[ "$S" = "complete" ] && ok "run complete" || { echo "run did not complete (status=$S)"; exit 1; }

echo "== report =="
curl -fsS "$API/runs/$RID/report" -X POST >/dev/null
curl -fsS "$API/runs/$RID/report" | python3 -c 'import sys,json;r=json.load(sys.stdin);assert r["summary"] and r["keyFindings"];print("report ok")'

echo "== chat =="
curl -fsS -X POST "$API/runs/$RID/chat/report" -H 'Content-Type: application/json' -d '{"message":"what is the single biggest risk?"}' | grep -q '"reply"' && ok "report chat"

echo "ALL SMOKE TESTS PASSED"
