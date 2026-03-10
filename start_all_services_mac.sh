#!/usr/bin/env bash
# Full Backend Stack Launcher for SCS Dashboard (macOS/Linux)
# Starts all required services in background and writes logs under ./logs.
# Usage:
#   bash start_all_services_mac.sh        # start services
#   bash start_all_services_mac.sh stop   # stop services started by this script

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$PROJECT_ROOT/logs"
PID_FILE="$PROJECT_ROOT/.all_services_mac.pids"

# OAuth config file used by auth-service
AUTH_ENV_FILE="$PROJECT_ROOT/.env.auth"

# Bootstrap Python used only to create per-service virtualenvs.
if [[ -x "$PROJECT_ROOT/.venv/bin/python" ]]; then
  BOOTSTRAP_PYTHON="$PROJECT_ROOT/.venv/bin/python"
elif command -v python3.11 >/dev/null 2>&1; then
  BOOTSTRAP_PYTHON="$(command -v python3.11)"
elif command -v python3 >/dev/null 2>&1; then
  BOOTSTRAP_PYTHON="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  BOOTSTRAP_PYTHON="$(command -v python)"
else
  echo "[ERROR] Python not found. Install Python or create .venv first."
  exit 1
fi

mkdir -p "$LOG_DIR"

# Load OAuth client credentials from .env.auth when available.
OAUTH_CLIENT_ID=""
OAUTH_CLIENT_SECRET=""
if [[ -f "$AUTH_ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$AUTH_ENV_FILE"
  OAUTH_CLIENT_ID="${OAUTH_CLIENT_ID:-}"
  OAUTH_CLIENT_SECRET="${OAUTH_CLIENT_SECRET:-}"
fi

stop_services() {
  if [[ -f "$PID_FILE" ]]; then
    echo "Stopping services from $PID_FILE ..."
    while read -r pid; do
      if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null || true
        echo "  - stopped PID $pid"
      fi
    done < "$PID_FILE"
    rm -f "$PID_FILE"
    echo "All services stopped."
  else
    echo "No PID file found. Nothing to stop."
  fi
}

if [[ "${1:-}" == "stop" ]]; then
  stop_services
  exit 0
fi

# Stop previously started processes from this script before starting fresh.
if [[ -f "$PID_FILE" ]]; then
  echo "Existing PID file found. Stopping previous run first..."
  stop_services
fi

> "$PID_FILE"

setup_service_venv() {
  local name="$1"
  local dir="$2"
  local req_file="$dir/requirements.txt"
  local venv_dir="$dir/.venv"
  local stamp_file="$venv_dir/.requirements.sha256"

  if [[ ! -f "$req_file" ]]; then
    echo "[WARN] $name has no requirements.txt in $dir. Using bootstrap Python." >&2
    echo "$BOOTSTRAP_PYTHON"
    return 0
  fi

  if [[ ! -x "$venv_dir/bin/python" ]]; then
    echo "[SETUP] Creating venv for $name at $venv_dir" >&2
    "$BOOTSTRAP_PYTHON" -m venv "$venv_dir"
  fi

  local req_hash
  req_hash="$(shasum -a 256 "$req_file" | awk '{print $1}')"
  local old_hash=""
  if [[ -f "$stamp_file" ]]; then
    old_hash="$(cat "$stamp_file")"
  fi

  if [[ "$req_hash" != "$old_hash" ]]; then
    echo "[SETUP] Installing dependencies for $name from $req_file" >&2
    "$venv_dir/bin/python" -m pip install --quiet --upgrade pip setuptools wheel
    "$venv_dir/bin/python" -m pip install --quiet -r "$req_file"
    echo "$req_hash" > "$stamp_file"
  else
    echo "[SETUP] $name dependencies unchanged. Skipping pip install." >&2
  fi

  echo "$venv_dir/bin/python"
}

start_service() {
  local name="$1"
  local dir="$2"
  local module="$3"
  local port="$4"
  local logfile="$LOG_DIR/${name}.log"
  shift 4

  local service_python
  service_python="$(setup_service_venv "$name" "$dir")"

  (
    cd "$dir"
    env "$@" "$service_python" -m uvicorn "$module" --host 0.0.0.0 --port "$port" --reload
  ) >"$logfile" 2>&1 &

  local pid=$!
  echo "$pid" >> "$PID_FILE"
  echo "  -> started $name on :$port (PID $pid) [python: $service_python]"
}

echo ""
echo "Starting SCS backend services for macOS..."
echo "-------------------------------------------"

# auth-service
auth_env=(
  "PYTHONUNBUFFERED=1"
  "OAUTH_AUTHORIZE_URL=https://accounts.google.com/o/oauth2/v2/auth"
  "OAUTH_TOKEN_URL=https://oauth2.googleapis.com/token"
  "OAUTH_REDIRECT_URI=http://localhost:8001/callback"
  "FRONTEND_REDIRECT_URL=http://localhost:5173"
)
if [[ -n "$OAUTH_CLIENT_ID" ]]; then
  auth_env+=("OAUTH_CLIENT_ID=$OAUTH_CLIENT_ID")
fi
if [[ -n "$OAUTH_CLIENT_SECRET" ]]; then
  auth_env+=("OAUTH_CLIENT_SECRET=$OAUTH_CLIENT_SECRET")
fi
start_service "auth-service" "$PROJECT_ROOT/auth-service" "main:app" "8001" "${auth_env[@]}"

# case-service
start_service "case-service" "$PROJECT_ROOT/case-service" "app.main:app" "8003" \
  "PYTHONUNBUFFERED=1"

# chatbot-service
start_service "chatbot-service" "$PROJECT_ROOT/chatbot-service" "app.main:app" "8000" \
  "PYTHONUNBUFFERED=1"

# mcp-service
start_service "mcp-service" "$PROJECT_ROOT/mcp-service" "app.main:app" "8002" \
  "PYTHONUNBUFFERED=1"

# scraper-service
start_service "scraper-service" "$PROJECT_ROOT/scraper-service" "app:app" "8005" \
  "PYTHONUNBUFFERED=1"

# backend-api
start_service "backend-api" "$PROJECT_ROOT/backend" "app:app" "8004" \
  "PYTHONUNBUFFERED=1"

# image-service
start_service "image-service" "$PROJECT_ROOT/backend/image-service" "api.main:app" "8006" \
  "PYTHONUNBUFFERED=1"

# api-gateway
start_service "api-gateway" "$PROJECT_ROOT/api-gateway" "main:app" "8010" \
  "PYTHONUNBUFFERED=1" \
  "AUTH_SERVICE_URL=http://localhost:8001" \
  "SCRAPER_SERVICE_URL=http://localhost:8005" \
  "ANALYSIS_SERVICE_URL=http://localhost:8004/api/unified-pipeline/analyze-user" \
  "CHATBOT_SERVICE_URL=http://localhost:8000" \
  "IMAGE_SERVICE_URL=http://localhost:8006" \
  "MCP_SERVICE_URL=http://localhost:8002" \
  "CASE_SERVICE_URL=http://localhost:8003"

echo ""
echo "Waiting for services to initialize..."
sleep 6

echo ""
echo "Service health checks:"
for port in 8001 8003 8000 8002 8005 8004 8006 8010; do
  if curl -fsS "http://localhost:${port}/health" >/dev/null 2>&1; then
    echo "  [OK] http://localhost:${port}/health"
  else
    echo "  [..] http://localhost:${port}/health (starting or unavailable)"
  fi
done

echo ""
echo "Frontend Development Server:"
echo "  npm run dev"
echo "  URL: http://localhost:5173"
echo ""
echo "OAuth Login Flow:"
echo "  1. Open http://localhost:5173"
echo "  2. Click 'Sign in with Google OAuth'"
echo "  3. Complete OAuth and return to app"
echo ""
echo "API Documentation:"
echo "  Gateway:  http://localhost:8010/docs"
echo "  Case:     http://localhost:8003/docs"
echo "  Chatbot:  http://localhost:8000/docs"
echo "  Backend:  http://localhost:8004/docs"
echo ""
echo "Logs: tail -f logs/*.log"
echo "Stop: bash start_all_services_mac.sh stop"

# Keep script alive and cleanup on Ctrl+C.
cleanup() {
  echo ""
  echo "Stopping all services..."
  stop_services
}
trap cleanup INT TERM

while true; do
  sleep 60
done
