#!/usr/bin/env bash
# Run all three SCS services locally without Docker.
# Creates a shared .venv per service under each service directory.
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

load_env() {
  # Export every non-comment line from .env, substituting Docker service
  # hostnames with localhost so that services can reach each other locally.
  set -a
  # shellcheck disable=SC1090
  source <(grep -v '^\s*#' "$ENV_FILE" | grep -v '^\s*$' \
    | sed 's|http://case-service:|http://localhost:|g' \
    | sed 's|http://chatbot-service:|http://localhost:|g' \
    | sed 's|http://mcp-service:|http://localhost:|g')
  set +a
}

# ── stop ─────────────────────────────────────────────────────────────
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

# ── setup venv for a service ─────────────────────────────────────────
setup_venv() {
  local svc_dir="$1"
  local venv="$svc_dir/.venv"
  if [[ ! -d "$venv" ]]; then
    log "Creating venv for $(basename "$svc_dir")…"
    python3 -m venv "$venv"
  fi
  "$venv/bin/pip" install --quiet --upgrade pip
  "$venv/bin/pip" install --quiet -r "$svc_dir/requirements.txt"
}

# ── start a service ──────────────────────────────────────────────────
start_service() {
  local name="$1"
  local svc_dir="$2"
  local port="$3"
  local module="$4"           # e.g. app.main:app
  local log_file="$ROOT/logs/${name}.log"

  mkdir -p "$ROOT/logs"
  local venv="$svc_dir/.venv"

  log "Starting $name on :$port …"
  cd "$svc_dir"
  "$venv/bin/uvicorn" "$module" \
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
mkdir -p "$ROOT/data"  # shared SQLite + ChromaDB dir (normally /data in Docker)
load_env

# Override CASE_DB_PATH and CHROMA_PERSIST_DIR to use local ./data/
export CASE_DB_PATH="$ROOT/data/cases.db"
export CHROMA_PERSIST_DIR="$ROOT/data/chromadb"
export DOCS_DIR="$ROOT/chatbot-service/docs"

log "Installing dependencies…"
setup_venv "$ROOT/case-service"
setup_venv "$ROOT/chatbot-service"
setup_venv "$ROOT/mcp-service"

log "Launching services…"
start_service "case-service"    "$ROOT/case-service"    "${CASE_SERVICE_PORT:-8001}"    "app.main:app"
sleep 2   # give case-service time to seed before chatbot tries to fetch cases

start_service "chatbot-service" "$ROOT/chatbot-service" "${CHATBOT_SERVICE_PORT:-8002}"  "app.main:app"
start_service "mcp-service"     "$ROOT/mcp-service"     "${MCP_SERVICE_PORT:-8003}"      "app.main:app"

echo ""
ok "All services running:"
ok "  case-service    → http://localhost:${CASE_SERVICE_PORT:-8001}/docs"
ok "  chatbot-service → http://localhost:${CHATBOT_SERVICE_PORT:-8002}/docs"
ok "  mcp-service     → http://localhost:${MCP_SERVICE_PORT:-8003}/docs"
echo ""
log "Frontend: cd $(basename $ROOT) && npm run dev"
log "Stop all: bash start_dev.sh stop"
log "Tail logs: tail -f logs/case-service.log"
