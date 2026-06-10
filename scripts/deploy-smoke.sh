#!/usr/bin/env bash
# Deploy smoke test — verify a deploy ACTUALLY took, not just that the host is up.
#
# Catches the "stale image" class of failure (docs/24-deploy-runbook.md): a stale
# backend answers /healthz fine but 404s on routes only the new code has. So we
# probe a new-code route, the CORS allow-origin the frontend needs, and the
# frontend canonical. Any failed check -> non-zero exit.
#
# Usage:
#   scripts/deploy-smoke.sh                         # prod defaults
#   API=http://127.0.0.1:8000 WEB=http://localhost:3000 scripts/deploy-smoke.sh
#
# Env overrides:
#   API           backend base URL   (default: prod Railway)
#   WEB           frontend base URL  (default: prod Vercel canonical)
#   PROBE_ROUTE   a route only current code serves (default: /report)
set -u

API="${API:-https://strata-api-production-9740.up.railway.app}"
WEB="${WEB:-https://stratabank.vercel.app}"
PROBE_ROUTE="${PROBE_ROUTE:-/report}"
TIMEOUT=15
fail=0

note() { printf '  %s\n' "$1"; }
ok()   { printf '\033[32mPASS\033[0m %s\n' "$1"; }
bad()  { printf '\033[31mFAIL\033[0m %s\n' "$1"; fail=1; }

code() { curl -s -o /dev/null -w '%{http_code}' -m "$TIMEOUT" "$1" 2>/dev/null; }

# Retry a GET up to 4x for a 200 — absorbs Railway/Vercel cold-start 502s so a
# warming dyno doesn't read as a failed deploy. Echoes the last status code.
code_retry() {
  local c
  for _ in 1 2 3 4; do
    c=$(code "$1")
    [ "$c" = "200" ] && { echo "$c"; return; }
    sleep 3
  done
  echo "$c"
}

echo "== backend $API =="

# 1. Host is up at all (retry through cold-start 502s).
h=$(code_retry "$API/healthz")
[ "$h" = "200" ] && ok "/healthz -> 200" || bad "/healthz -> $h (backend down?)"

# 2. New-code route — the stale-image detector. A pre-report-engine image 404s here.
p=$(code_retry "$API$PROBE_ROUTE")
[ "$p" = "200" ] && ok "$PROBE_ROUTE -> 200 (new code is live)" \
  || bad "$PROBE_ROUTE -> $p (STALE IMAGE? route missing — redeploy, see docs/24-deploy-runbook.md)"

# 3. CORS — the frontend's fetches are blocked without a matching allow-origin.
acao=$(curl -s -m "$TIMEOUT" -o /dev/null -D - -X OPTIONS "$API/c" \
  -H "Origin: $WEB" -H "Access-Control-Request-Method: GET" 2>/dev/null \
  | tr -d '\r' | awk -F': ' 'tolower($1)=="access-control-allow-origin"{print $2}')
if [ "$acao" = "$WEB" ] || [ "$acao" = "*" ]; then
  ok "CORS allow-origin for $WEB ($acao)"
else
  bad "CORS allow-origin = '${acao:-<none>}' (frontend fetches will be blocked)"
fi

echo "== frontend $WEB =="

# 4. Frontend: the web surface is landing + auth + OAuth consent only — probe
# the landing and the sign-in page.
w=$(code "$WEB/")
[ "$w" = "200" ] && ok "/ -> 200" || bad "/ -> $w (frontend down?)"

s=$(code "$WEB/sign-in")
[ "$s" = "200" ] && ok "/sign-in -> 200" || bad "/sign-in -> $s (auth page broken?)"

echo
if [ "$fail" -eq 0 ]; then
  echo "deploy smoke: all checks passed"
else
  echo "deploy smoke: FAILURES above — the deploy may not have taken. See docs/24-deploy-runbook.md"
fi
exit "$fail"
