#!/usr/bin/env bash
# run_inferno.sh — Headless Inferno US Core 6.1.0 test runner for gen3-fhir-proxy.
#
# Prerequisites:
#   1. gen3-fhir-proxy + Fence running locally (via start_gen3.sh in gen3-fhir-proxy).
#   2. us-core-test-kit repo checked out at $US_CORE_TEST_KIT_DIR (default: ~/us-core-test-kit).
#        Ruby 3.3.x required (see us-core-test-kit/.ruby-version). Use rbenv:
#          rbenv install 3.3.6 && rbenv global 3.3.6
#          gem install bundler:2.5.22
#          cd ~/us-core-test-kit && bundle install
#        Ensure rbenv shims are active (`eval "$(rbenv init -)"` in ~/.zshrc) so that
#        `bundle` resolves to the rbenv-managed version, not /usr/bin/bundle (system Ruby 2.6).
#   3. Client IDs written to ~/.gen3-fhir-proxy-clients.env (by gen3-fhir-proxy/dev_scripts/start_gen3.sh).
#   4. brew dependencies (macOS): brew install gettext foreman jq
#   5. Docker Desktop running (for Inferno's background services).
#
# Usage:
#   # Source client IDs first (written by gen3-fhir-proxy/dev_scripts/start_gen3.sh):
#   source ~/.gen3-fhir-proxy-clients.env
#   bash inferno-uscore/run_inferno.sh
#
# Options:
#   --us-core-dir PATH   Path to us-core-test-kit repo (default: ~/us-core-test-kit)
#   --no-services        Skip starting/stopping Inferno background services (useful when
#                        already running from a previous invocation)

set -Eeuo pipefail

# Initialize rbenv if present so `bundle` resolves to the rbenv-managed version
# even when this script is invoked as `bash run_inferno.sh` (no .zshrc sourced).
if command -v rbenv >/dev/null 2>&1; then
  eval "$(rbenv init -)"
fi

# ── Configuration ─────────────────────────────────────────────────────────────
_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

US_CORE_TEST_KIT_DIR="${US_CORE_TEST_KIT_DIR:-${HOME}/us-core-test-kit}"
INFERNO_FHIR_ENDPOINT="${INFERNO_FHIR_ENDPOINT:-http://host.docker.internal:8081/fhir}"
INFERNO_CLIENTS_ENV_FILE="${INFERNO_CLIENTS_ENV_FILE:-${HOME}/.gen3-fhir-proxy-clients.env}"
INFERNO_PORT="${INFERNO_PORT:-4567}"
INFERNO_LOG="${INFERNO_LOG:-/tmp/inferno_gen3.log}"
EXECUTION_YAML_OUT="${EXECUTION_YAML_OUT:-/tmp/gen3_fhir_proxy_610_smart_2.yaml}"
# Expected results file for inferno execute_script comparison.
# Lives next to the template in the repo so it persists across reboots and can be
# committed as the CI baseline. Override with INFERNO_EXPECTED_RESULTS_FILE env var.
INFERNO_EXPECTED_RESULTS_FILE="${INFERNO_EXPECTED_RESULTS_FILE:-${_SCRIPT_DIR}/execution_scripts/gen3_fhir_proxy/gen3_fhir_proxy_610_smart_2_expected.json}"
MANAGE_SERVICES="${MANAGE_SERVICES:-true}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --us-core-dir) US_CORE_TEST_KIT_DIR="$2"; shift 2 ;;
    --no-services) MANAGE_SERVICES="false"; shift ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

log()  { echo; echo "=== $* ==="; }
die()  { echo "ERROR: $*" >&2; exit 1; }
info() { echo "  → $*"; }

# ── Validate prerequisites ────────────────────────────────────────────────────
log "0 Validate prerequisites"

[ -d "$US_CORE_TEST_KIT_DIR" ] || die "us-core-test-kit not found at: $US_CORE_TEST_KIT_DIR (set US_CORE_TEST_KIT_DIR)"
[ -f "$US_CORE_TEST_KIT_DIR/Gemfile" ] || die "No Gemfile in $US_CORE_TEST_KIT_DIR — is this the right directory?"

# Load client IDs from env file if not already set
if [ -z "${INFERNO_CLIENT_ID:-}" ] && [ -f "$INFERNO_CLIENTS_ENV_FILE" ]; then
  info "Sourcing client IDs from $INFERNO_CLIENTS_ENV_FILE"
  # shellcheck source=/dev/null
  source "$INFERNO_CLIENTS_ENV_FILE"
fi

[ -n "${INFERNO_CLIENT_ID:-}" ]           || die "INFERNO_CLIENT_ID not set. Run gen3-fhir-proxy/dev_scripts/start_gen3.sh first (it writes $INFERNO_CLIENTS_ENV_FILE)."
[ -n "${INFERNO_GRANULAR1_CLIENT_ID:-}" ] || die "INFERNO_GRANULAR1_CLIENT_ID not set."
[ -n "${INFERNO_GRANULAR2_CLIENT_ID:-}" ] || die "INFERNO_GRANULAR2_CLIENT_ID not set."

command -v envsubst >/dev/null 2>&1 || die "envsubst not found. Install: brew install gettext"
command -v foreman  >/dev/null 2>&1 || die "foreman not found. Install: brew install foreman"
command -v jq       >/dev/null 2>&1 || die "jq not found. Install: brew install jq"
command -v docker   >/dev/null 2>&1 || die "docker not found — Docker Desktop required."

# Verify gen3-fhir-proxy is reachable (via revproxy, through FHIR endpoint)
FHIR_CHECK_URL="${FHIR_CHECK_URL:-http://localhost:8081/fhir/metadata}"
info "Checking gen3-fhir-proxy is reachable at $FHIR_CHECK_URL ..."
if ! curl -sf --max-time 10 "$FHIR_CHECK_URL" >/dev/null 2>&1; then
  die "gen3-fhir-proxy is not responding at $FHIR_CHECK_URL. Make sure gen3-fhir-proxy/dev_scripts/start_gen3.sh has been run successfully."
fi
info "gen3-fhir-proxy is up."

# ── Sync gen3-specific Inferno scripts into us-core-test-kit ──────────────────
log "1 Sync gen3 Inferno scripts into us-core-test-kit"
mkdir -p "$US_CORE_TEST_KIT_DIR/execution_scripts/gen3_fhir_proxy"
mkdir -p "$US_CORE_TEST_KIT_DIR/config/presets"
cp "${_SCRIPT_DIR}/execution_scripts/gen3_fhir_proxy/"* \
   "$US_CORE_TEST_KIT_DIR/execution_scripts/gen3_fhir_proxy/"
cp "${_SCRIPT_DIR}/config/presets/gen3_fhir_proxy_610_preset.json" \
   "$US_CORE_TEST_KIT_DIR/config/presets/"
info "Synced execution scripts and preset from ${_SCRIPT_DIR}"

# ── Generate execution YAML from template ─────────────────────────────────────
log "2 Generate execution YAML"
TEMPLATE="${US_CORE_TEST_KIT_DIR}/execution_scripts/gen3_fhir_proxy/gen3_fhir_proxy_610_smart_2.yaml.template"
[ -f "$TEMPLATE" ] || die "Template not found: $TEMPLATE"

FENCE_DEV_LOGIN_USER="${FENCE_DEV_LOGIN_USER:-test}"
export INFERNO_CLIENT_ID INFERNO_GRANULAR1_CLIENT_ID INFERNO_GRANULAR2_CLIENT_ID INFERNO_FHIR_ENDPOINT FENCE_DEV_LOGIN_USER INFERNO_EXPECTED_RESULTS_FILE
# Restrict substitution to the variables the template actually uses, so that any
# other `$` in the template (regexes, {wait_outputs.*} placeholders) is left alone.
envsubst '${INFERNO_CLIENT_ID} ${INFERNO_GRANULAR1_CLIENT_ID} ${INFERNO_GRANULAR2_CLIENT_ID} ${INFERNO_FHIR_ENDPOINT} ${INFERNO_EXPECTED_RESULTS_FILE}' < "$TEMPLATE" > "$EXECUTION_YAML_OUT"

# Fail if any INFERNO_ placeholder was left unsubstituted (e.g. a new variable
# was added to the template but not to the envsubst list above).
if grep -n '\${INFERNO_' "$EXECUTION_YAML_OUT"; then
  die "Unsubstituted \${INFERNO_*} placeholders remain in $EXECUTION_YAML_OUT (see lines above)."
fi
info "Generated: $EXECUTION_YAML_OUT"

# ── Inferno background services ───────────────────────────────────────────────
INFERNO_PID=""

cleanup() {
  if [ -n "$INFERNO_PID" ] && kill -0 "$INFERNO_PID" 2>/dev/null; then
    info "Stopping Inferno (PID $INFERNO_PID)..."
    kill "$INFERNO_PID" 2>/dev/null || true
    wait "$INFERNO_PID" 2>/dev/null || true
  fi
  if [ "$MANAGE_SERVICES" = "true" ]; then
    info "Stopping Inferno background services..."
    (cd "$US_CORE_TEST_KIT_DIR" && bundle exec inferno services stop 2>/dev/null) || true
  fi
}
trap cleanup EXIT

cd "$US_CORE_TEST_KIT_DIR"

if [ "$MANAGE_SERVICES" = "true" ]; then
  log "3 Prepare Inferno data directories"
  mkdir -p data/redis
  chmod 777 data/redis

  log "4 Start Inferno background services (Redis + HL7 Validator + nginx)"
  bundle exec inferno services start

  info "Waiting for Redis..."
  for i in $(seq 1 30); do
    if docker compose -f docker-compose.background.yml exec -T redis redis-cli ping 2>/dev/null | grep -q PONG; then
      info "Redis is ready."
      break
    fi
    [ "$i" -eq 30 ] && die "Redis did not become ready in time."
    sleep 2
  done

  log "5 Run database migrations"
  bundle exec inferno migrate
fi

log "6 Start Inferno server"
bundle exec inferno start > "$INFERNO_LOG" 2>&1 &
INFERNO_PID=$!
info "Inferno starting (PID $INFERNO_PID, log: $INFERNO_LOG)..."

for i in $(seq 1 60); do
  if curl -sf "http://localhost:${INFERNO_PORT}" >/dev/null 2>&1; then
    info "Inferno is ready at http://localhost:${INFERNO_PORT}"
    break
  fi
  [ "$i" -eq 60 ] && die "Inferno did not start in time. Check log: $INFERNO_LOG"
  sleep 2
done

# ── Run the execution script ──────────────────────────────────────────────────
log "7 Execute Inferno test script"
echo ""
echo "  Client IDs in use:"
echo "    INFERNO_CLIENT_ID           = $INFERNO_CLIENT_ID"
echo "    INFERNO_GRANULAR1_CLIENT_ID = $INFERNO_GRANULAR1_CLIENT_ID"
echo "    INFERNO_GRANULAR2_CLIENT_ID = $INFERNO_GRANULAR2_CLIENT_ID"
echo "    INFERNO_FHIR_ENDPOINT       = $INFERNO_FHIR_ENDPOINT"
echo ""

# Under `set -e`, a bare failing command would exit before `EXIT_CODE=$?` runs,
# so capture the status with `||`.
EXIT_CODE=0
bundle exec inferno execute_script --allow-commands "$EXECUTION_YAML_OUT" || EXIT_CODE=$?

# When no expected results file exists, Inferno writes the full results dump (inputs,
# requests, messages, OAuth tokens — several MB). The comparison only uses the runnable
# id and result, so strip everything else to keep the committed baseline small and free
# of secrets.
if [ -f "$INFERNO_EXPECTED_RESULTS_FILE" ] && jq -e \
  'any(.[]; (keys - ["test_id", "test_group_id", "test_suite_id", "result"]) | length > 0)' \
  "$INFERNO_EXPECTED_RESULTS_FILE" >/dev/null; then
  _TRIMMED_EXPECTED="$(mktemp "${INFERNO_EXPECTED_RESULTS_FILE}.XXXXXX")"
  jq '[.[] | {test_id, test_group_id, test_suite_id, result} | with_entries(select(.value != null))]' \
    "$INFERNO_EXPECTED_RESULTS_FILE" > "$_TRIMMED_EXPECTED"
  mv "$_TRIMMED_EXPECTED" "$INFERNO_EXPECTED_RESULTS_FILE"
  info "Trimmed expected results file to runnable ids and results: $INFERNO_EXPECTED_RESULTS_FILE"
fi

echo ""
if [ "$EXIT_CODE" -eq 0 ]; then
  echo "✓ Inferno execution script completed successfully."
else
  echo "✗ Inferno execution script failed (exit code $EXIT_CODE)."
  echo "  Inferno server log: $INFERNO_LOG"
  echo "  --- last 50 lines of $INFERNO_LOG ---"
  tail -n 50 "$INFERNO_LOG" 2>/dev/null || true
  echo "  --- end of log tail ---"
fi

exit "$EXIT_CODE"
