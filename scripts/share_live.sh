#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5174}"
FRONTEND_HOST="${FRONTEND_HOST:-0.0.0.0}"
BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_HEALTH_TIMEOUT="${BACKEND_HEALTH_TIMEOUT:-180}"
FRONTEND_HEALTH_TIMEOUT="${FRONTEND_HEALTH_TIMEOUT:-120}"
TUNNEL_URL_TIMEOUT="${TUNNEL_URL_TIMEOUT:-60}"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG_DIR="${PROJECT_ROOT}/logs/share_live/${TIMESTAMP}"
mkdir -p "${LOG_DIR}"

BACKEND_LOG="${LOG_DIR}/backend.log"
BACKEND_TUNNEL_LOG="${LOG_DIR}/backend_tunnel.log"
FRONTEND_LOG="${LOG_DIR}/frontend.log"
FRONTEND_TUNNEL_LOG="${LOG_DIR}/frontend_tunnel.log"

PIDS=()

require_cmd() {
  local name="$1"
  if ! command -v "${name}" >/dev/null 2>&1; then
    echo "Missing required command: ${name}" >&2
    exit 1
  fi
}

cleanup() {
  local exit_code="$?"
  trap - EXIT INT TERM
  for pid in "${PIDS[@]:-}"; do
    if kill -0 "${pid}" >/dev/null 2>&1; then
      kill "${pid}" >/dev/null 2>&1 || true
    fi
  done
  wait >/dev/null 2>&1 || true
  if [[ "${exit_code}" -ne 0 ]]; then
    echo
    echo "share_live failed. Check logs:"
    echo "  ${LOG_DIR}"
  fi
  exit "${exit_code}"
}
trap cleanup EXIT INT TERM

wait_for_http() {
  local url="$1"
  local timeout_seconds="$2"
  local i
  for ((i = 1; i <= timeout_seconds; i += 1)); do
    if curl -fsS -m 2 "${url}" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

extract_trycloudflare_url() {
  local logfile="$1"
  local timeout_seconds="$2"
  local i
  local url
  for ((i = 1; i <= timeout_seconds; i += 1)); do
    if [[ -f "${logfile}" ]]; then
      url="$(grep -Eo 'https://[A-Za-z0-9.-]+\.trycloudflare\.com' "${logfile}" | head -n 1 || true)"
      if [[ -n "${url}" ]]; then
        echo "${url}"
        return 0
      fi
    fi
    sleep 1
  done
  return 1
}

print_log_tail() {
  local label="$1"
  local logfile="$2"
  echo
  echo "--- ${label} (${logfile}) ---"
  tail -n 80 "${logfile}" || true
}

require_cmd curl
require_cmd cloudflared
require_cmd npm

if [[ ! -f "${PROJECT_ROOT}/.venv/bin/activate" ]]; then
  echo "Python virtualenv not found at ${PROJECT_ROOT}/.venv." >&2
  exit 1
fi

if [[ ! -f "${PROJECT_ROOT}/webapp/package.json" ]]; then
  echo "webapp/package.json not found. Run this script from the project checkout." >&2
  exit 1
fi

echo "Starting backend on ${BACKEND_HOST}:${BACKEND_PORT}..."
(
  cd "${PROJECT_ROOT}"
  source .venv/bin/activate
  export CORS_ALLOW_ORIGIN_REGEX="${CORS_ALLOW_ORIGIN_REGEX:-^https://.*\\.trycloudflare\\.com$}"
  uvicorn api.main:app --host "${BACKEND_HOST}" --port "${BACKEND_PORT}"
) >"${BACKEND_LOG}" 2>&1 &
PIDS+=("$!")

if ! wait_for_http "http://${BACKEND_HOST}:${BACKEND_PORT}/health" "${BACKEND_HEALTH_TIMEOUT}"; then
  print_log_tail "backend startup" "${BACKEND_LOG}"
  echo "Backend failed health check within ${BACKEND_HEALTH_TIMEOUT}s." >&2
  exit 1
fi

echo "Opening backend tunnel..."
cloudflared tunnel --url "http://${BACKEND_HOST}:${BACKEND_PORT}" >"${BACKEND_TUNNEL_LOG}" 2>&1 &
PIDS+=("$!")

BACKEND_PUBLIC_URL="$(extract_trycloudflare_url "${BACKEND_TUNNEL_LOG}" "${TUNNEL_URL_TIMEOUT}" || true)"
if [[ -z "${BACKEND_PUBLIC_URL}" ]]; then
  print_log_tail "backend tunnel" "${BACKEND_TUNNEL_LOG}"
  echo "Unable to obtain backend public URL." >&2
  exit 1
fi

echo "Starting frontend on ${FRONTEND_HOST}:${FRONTEND_PORT}..."
(
  cd "${PROJECT_ROOT}/webapp"
  VITE_API_BASE_URL="${BACKEND_PUBLIC_URL}" npm run dev -- --host "${FRONTEND_HOST}" --port "${FRONTEND_PORT}"
) >"${FRONTEND_LOG}" 2>&1 &
PIDS+=("$!")

if ! wait_for_http "http://127.0.0.1:${FRONTEND_PORT}" "${FRONTEND_HEALTH_TIMEOUT}"; then
  print_log_tail "frontend startup" "${FRONTEND_LOG}"
  echo "Frontend failed health check within ${FRONTEND_HEALTH_TIMEOUT}s." >&2
  exit 1
fi

echo "Opening frontend tunnel..."
cloudflared tunnel --url "http://127.0.0.1:${FRONTEND_PORT}" >"${FRONTEND_TUNNEL_LOG}" 2>&1 &
PIDS+=("$!")

FRONTEND_PUBLIC_URL="$(extract_trycloudflare_url "${FRONTEND_TUNNEL_LOG}" "${TUNNEL_URL_TIMEOUT}" || true)"
if [[ -z "${FRONTEND_PUBLIC_URL}" ]]; then
  print_log_tail "frontend tunnel" "${FRONTEND_TUNNEL_LOG}"
  echo "Unable to obtain frontend public URL." >&2
  exit 1
fi

echo
echo "=============================================="
echo "TradeIQ Live Share Ready"
echo "----------------------------------------------"
echo "Frontend URL (share this): ${FRONTEND_PUBLIC_URL}"
echo "Backend URL:               ${BACKEND_PUBLIC_URL}"
echo "Logs:                      ${LOG_DIR}"
echo "Press Ctrl+C to stop all processes."
echo "=============================================="
echo

while true; do
  sleep 5
  for pid in "${PIDS[@]}"; do
    if ! kill -0 "${pid}" >/dev/null 2>&1; then
      echo "A background process exited unexpectedly (pid=${pid})." >&2
      exit 1
    fi
  done
done
