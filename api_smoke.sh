#!/usr/bin/env bash
set -euo pipefail
K=supersecret1
BASE="http://localhost:8000/api/v1"

curl -fsS "$BASE/health" | jq .
curl -fsS -H "X-API-Key: $K" "$BASE/symbols/?limit=2" | jq .
curl -fsS -H "X-API-Key: $K" "$BASE/ohlcv/?symbol_id=1&candle_width=1d&limit=2" | jq .
curl -fsS -H "X-API-Key: $K" "$BASE/indicators/?symbol_id=1&candle_width=1d&limit=2" | jq .
curl -fsS -H "X-API-Key: $K" "$BASE/indicator-series/?symbol_id=1&candle_width=1d&indicator_name=SMA&window_size=20&limit=2" | jq .

# anchors
MS=$(( $(date +%s) * 1000 ))
A=$(curl -fsS -H "X-API-Key: $K" -H "Content-Type: application/json" \
  -d "{\"symbol_id\":1,\"candle_width\":\"1d\",\"anchor_type\":\"custom_event\",\"anchor_ms\":$MS,\"anchor_label\":\"test\"}" \
  "$BASE/anchors/?on_conflict=return")
echo "$A" | jq .
ID=$(echo "$A" | jq -r .anchor_id)
curl -fsS -H "X-API-Key: $K" -H "Content-Type: application/json" \
  -X PATCH -d '{"anchor_label":"test-upd"}' "$BASE/anchors/$ID" | jq .
curl -fsS -H "X-API-Key: $K" -X DELETE "$BASE/anchors/$ID" -i | sed -n '1,1p'

# sync-meta upsert
curl -fsS -H "X-API-Key: $K" -H "Content-Type: application/json" \
  -X PATCH -d "{\"last_backfill_ms\":$MS}" "$BASE/sync-meta/1/1d" | jq .

# job-runs
JR=$(curl -fsS -H "X-API-Key: $K" -H "Content-Type: application/json" \
  -d '{"job_name":"backfill","run_status":"warning","symbol_id":1,"candle_width":"1d","log_message":"starting..."}' \
  "$BASE/job-runs/")
echo "$JR" | jq .
JID=$(echo "$JR" | jq -r .job_id)
curl -fsS -H "X-API-Key: $K" -H "Content-Type: application/json" \
  -X PATCH -d "{\"run_status\":\"success\",\"finished_ms\":$MS,\"rows_affected\":123}" \
  "$BASE/job-runs/$JID" | jq .