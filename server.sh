#!/usr/bin/env bash
# Labin Strike server control script: start | stop | restart | status
set -uo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${PORT:-7344}"
PID_FILE="$APP_DIR/server.pid"
LOG_FILE="$APP_DIR/server.log"
NODE_BIN="${NODE_BIN:-$(command -v node || true)}"
ENTRY="server/index.js"
STOP_TIMEOUT="${STOP_TIMEOUT:-10}"

red() { printf '\033[31m%s\033[0m\n' "$*"; }
green() { printf '\033[32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[33m%s\033[0m\n' "$*"; }

# Prints the PID from the pid file if that process is alive and is our server.
running_pid() {
  [[ -f "$PID_FILE" ]] || return 1
  local pid
  pid="$(tr -dc '0-9' < "$PID_FILE")"
  [[ -n "$pid" ]] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  ps -p "$pid" -o command= 2>/dev/null | grep -q "$ENTRY" || return 1
  echo "$pid"
}

port_listening() {
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1 && return 0
  fi
  if command -v ss >/dev/null 2>&1; then
    ss -ltn 2>/dev/null | awk '{print $4}' | grep -Eq "[:.]$PORT\$" && return 0
  fi
  if command -v nc >/dev/null 2>&1; then
    nc -z 127.0.0.1 "$PORT" >/dev/null 2>&1 && return 0
  fi
  return 1
}

do_start() {
  local pid
  if pid="$(running_pid)"; then
    yellow "Server already running (PID $pid). Use '$0 restart' to restart it."
    return 1
  fi
  if [[ -f "$PID_FILE" ]]; then
    yellow "Removing stale pid file."
    rm -f "$PID_FILE"
  fi
  if [[ ! -f "$APP_DIR/dist/index.html" ]]; then
    red "No production build found (dist/index.html). Run 'npm run build' first."
    return 1
  fi
  if [[ ! -d "$APP_DIR/node_modules" ]]; then
    red "node_modules missing. Run 'npm install' first."
    return 1
  fi
  if [[ -z "$NODE_BIN" ]]; then
    red "node not found in PATH (set NODE_BIN)."
    return 1
  fi
  if port_listening; then
    red "Port $PORT is already in use by another process."
    return 1
  fi

  cd "$APP_DIR" || return 1
  echo "--- $(date '+%Y-%m-%d %H:%M:%S') starting server ---" >> "$LOG_FILE"
  # Detach fully: new session where available, ignore hangups, no tty attached.
  if command -v setsid >/dev/null 2>&1; then
    NODE_ENV=production PORT="$PORT" nohup setsid "$NODE_BIN" "$ENTRY" >> "$LOG_FILE" 2>&1 < /dev/null &
  else
    NODE_ENV=production PORT="$PORT" nohup "$NODE_BIN" "$ENTRY" >> "$LOG_FILE" 2>&1 < /dev/null &
  fi
  pid=$!
  disown "$pid" 2>/dev/null || true
  echo "$pid" > "$PID_FILE"

  # Catch immediate crashes (missing deps, syntax errors) without blocking.
  sleep 1
  if ! kill -0 "$pid" 2>/dev/null; then
    rm -f "$PID_FILE"
    red "Server exited immediately. Last log lines:"
    tail -n 15 "$LOG_FILE"
    return 1
  fi
  green "Server started (PID $pid) on port $PORT. Logs: $LOG_FILE"
}

do_stop() {
  local pid
  if ! pid="$(running_pid)"; then
    yellow "Server is not running."
    rm -f "$PID_FILE"
    return 0
  fi
  echo "Stopping server (PID $pid) with SIGTERM..."
  kill -TERM "$pid" 2>/dev/null
  local waited=0
  while kill -0 "$pid" 2>/dev/null && (( waited < STOP_TIMEOUT * 10 )); do
    sleep 0.1
    waited=$((waited + 1))
  done
  if kill -0 "$pid" 2>/dev/null; then
    yellow "Still alive after ${STOP_TIMEOUT}s, sending SIGKILL."
    kill -KILL "$pid" 2>/dev/null
    sleep 0.5
  fi
  rm -f "$PID_FILE"
  green "Server stopped."
}

do_status() {
  local pid rc=0
  if pid="$(running_pid)"; then
    green "Process: running (PID $pid)"
  else
    red "Process: not running"
    rc=1
  fi
  if port_listening; then
    green "Port $PORT: listening"
  else
    red "Port $PORT: not listening"
    rc=1
  fi
  return $rc
}

case "${1:-}" in
  start) do_start ;;
  stop) do_stop ;;
  restart) do_stop && do_start ;;
  status) do_status ;;
  *) echo "Usage: $0 {start|stop|restart|status}"; exit 2 ;;
esac
