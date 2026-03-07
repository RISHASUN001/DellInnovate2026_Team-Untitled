#!/usr/bin/env bash
# Run all three SCS services locally without Docker.
# Works on Mac/Linux and Windows (Git Bash, WSL).
# Usage: bash start_dev.sh        — start all services
#        bash start_dev.sh stop   — kill all services started by this script

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$ROOT/.env"
PID_FILE="$ROOT/.dev_pids"

# ── helpers ──────────────────────────────────────────────────────────
log()  { echo -e "\033[1;36m[start_dev]\033[0m $*"; }
ok()   { echo -e "\033[1;32m[OK]\033[0m $*"; }
err()  { echo -e "\033[1;31m[ERR]\033[0m $*"; }

# ── detect python command ─────────────────────────────────────────────
detect_python() {
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
  else
    err "Python not found in PATH!"
    exit 1
  fi
  log "Using Python: $($PYTHON_CMD --version | tr -d '\n')"
}

# ── load .env ───────────────────────────────────────────────────────
load_env() {
  set -a
  source <(grep -v '^\s*#' "$ENV_FILE" | grep -v '^\s*$' \
    | sed 's|http://case-service:|http://localhost:|g' \
    | sed 's|http://chatbot-service:|http://localhost:|g' \
    | sed 's|http://mcp-service:|http://localhost:|g')
  set +a
}

# ── stop services ───────────────────────────────────────────────────
if [[ "${1:-}" == "stop" ]]; then
  if [[ -f "$PID_FILE" ]]; then
    while read -r pid; do
      kill "$pid" 2>/dev/null && log "Killed PID $pid" || true
    done < "$PID_FILE"
    rm -f "$PID_FILE"
    ok "All services stopped."
  else
    log "No PID file found — nothing to stop."
  fi
  exit 0
fi

# ── setup virtual environment ───────────────────────────────────────
setup_venv() {
  local svc_dir="$1"
  local venv="$svc_dir/.venv"

  if [[ ! -d "$venv" ]]; then
    log "Creating venv for $(basename "$svc_dir")…"
    "$PYTHON_CMD" -m venv "$venv"

    # Bootstrap pip if missing (Windows or Python install without ensurepip)
    if [[ ! -f "$venv/bin/pip" && ! -f "$venv/Scripts/pip.exe" ]]; then
      log "Bootstrapping pip in venv…"
      "$PYTHON_CMD" -m ensurepip --upgrade || true
    fi
  fi

  # Determine pip and uvicorn paths
  if [[ -f "$venv/bin/pip" ]]; then
      PIP="$venv/bin/pip"
      UVICORN="$venv/bin/uvicorn"
  elif [[ -f "$venv/Scripts/pip.exe" ]]; then
      PIP="$venv/Scripts/pip.exe"
      UVICORN="$venv/Scripts/uvicorn.exe"
  else
      err "Cannot find pip in virtual environment!"
      exit 1
  fi

  "$PIP" install --quiet --upgrade pip
  "$PIP" install --quiet -r "$svc_dir/requirements.txt"
}

# ── start service ───────────────────────────────────────────────────
start_service() {
  local name="$1"
  local svc_dir="$2"
  local port="$3"
  local module="$4"
  local log_file="$ROOT/logs/${name}.log"

  mkdir -p "$ROOT/logs"
  log "Starting $name on :$port …"
  cd "$svc_dir"
  "$UVICORN" "$module" \
    --host 0.0.0.0 \
    --port "$port" \
    --reload \
    > "$log_file" 2>&1 &
  local pid=$!
  echo "$pid" >> "$PID_FILE"
  ok "$name started (PID $pid) — logs: logs/${name}.log"
  cd "$ROOT"
}

# ── main ─────────────────────────────────────────────────────────────
> "$PID_FILE"          # reset PID file
mkdir -p "$ROOT/data"  # shared SQLite + ChromaDB dir

detect_python
load_env

# Override local paths
export CASE_DB_PATH="$ROOT/data/cases.db"
export CHROMA_PERSIST_DIR="$ROOT/data/chromadb"
export DOCS_DIR="$ROOT/chatbot-service/docs"

log "Installing dependencies…"
setup_venv "$ROOT/case-service"
setup_venv "$ROOT/chatbot-service"
setup_venv "$ROOT/mcp-service"

log "Launching services…"
start_service "case-service"    "$ROOT/case-service"    "${CASE_SERVICE_PORT:-8003}"    "app.main:app"
sleep 2
start_service "chatbot-service" "$ROOT/chatbot-service" "${CHATBOT_SERVICE_PORT:-8000}"  "app.main:app"
start_service "mcp-service"     "$ROOT/mcp-service"     "${MCP_SERVICE_PORT:-8002}"      "app.main:app"

echo ""
ok "All services running:"
ok "  case-service    → http://localhost:${CASE_SERVICE_PORT:-8003}/docs"
ok "  chatbot-service → http://localhost:${CHATBOT_SERVICE_PORT:-8000}/docs"
ok "  mcp-service     → http://localhost:${MCP_SERVICE_PORT:-8002}/docs"
echo ""
log "Waiting for services to be ready..."
sleep 3

# Health check
log "Testing service health..."
curl -s http://localhost:8003/health && ok "✓ case-service healthy" || err "✗ case-service not responding"
curl -s http://localhost:8000/health && ok "✓ chatbot-service healthy" || err "✗ chatbot-service not responding"
curl -s http://localhost:8002/health && ok "✓ mcp-service healthy" || err "✗ mcp-service not responding"
echo ""
log "Frontend: cd $(basename $ROOT) && npm run dev"
log "Stop all: bash start_dev.sh stop"
log "Run tests: bash run_tests.sh"
log "Tail logs: tail -f logs/case-service.log logs/chatbot-service.log logs/mcp-service.log"
echo ""
ok " All systems ready!"