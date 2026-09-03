#!/usr/bin/env bash
# fusion-health lifecycle manager (start|stop|restart|status|doctor)
# REST API on port 11469 (health endpoint: /health, 公开无需鉴权)。
# Callers: fusion-studio UpstreamServiceManager (auto-start on launch + manual start)。
# Affected API: start.sh start|stop|restart|status|doctor; status exits 0 if running, 1 if not。
# Data schemas: PID file .fusion-health.pid; logs/stdout.log + logs/stderr.log。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PID_FILE="${SCRIPT_DIR}/.fusion-health.pid"
LOG_DIR="${SCRIPT_DIR}/logs"
STDOUT_LOG="${LOG_DIR}/stdout.log"
STDERR_LOG="${LOG_DIR}/stderr.log"
PORT="${FUSION_HEALTH_PORT:-11469}"
HOST="${FUSION_HEALTH_HOST:-127.0.0.1}"

mkdir -p "$LOG_DIR"

log_info()  { printf "\033[0;32m[INFO]\033[0m  %s\n" "$*"; }
log_error() { printf "\033[0;31m[ERROR]\033[0m %s\n" "$*"; }
log_warn()  { printf "\033[0;33m[WARN]\033[0m  %s\n" "$*"; }

is_running() {
    [ -f "$PID_FILE" ] || return 1
    local pid
    pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    [ -n "$pid" ] || return 1
    kill -0 "$pid" 2>/dev/null
}

ensure_venv() {
    local venv="${FUSION_HEALTH_VENV:-/Users/dahai/fusion/.venv}"
    if [[ -f "${venv}/bin/activate" ]]; then
        # shellcheck disable=SC1091
        source "${venv}/bin/activate"
    else
        log_error "venv not found at ${venv} (set FUSION_HEALTH_VENV)"
        return 1
    fi
}

port_in_use() {
    if command -v lsof >/dev/null 2>&1; then
        lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1
    elif command -v nc >/dev/null 2>&1; then
        nc -z 127.0.0.1 "$PORT" >/dev/null 2>&1
    else
        return 1
    fi
}

check_api_key() {
    if [[ -z "${FUSION_HEALTH_API_KEY:-}" ]]; then
        log_warn "FUSION_HEALTH_API_KEY not set — API will accept only localhost clients"
        log_warn "Remote (non-127.0.0.1) requests return 401. Set FUSION_HEALTH_API_KEY for remote access."
    fi
}

do_start() {
    if is_running; then
        log_info "fusion-health already running (pid $(cat "$PID_FILE"))"
        return 0
    fi
    ensure_venv
    if port_in_use; then
        log_error "port ${PORT} already in use — refusing to start (set FUSION_HEALTH_PORT to change)"
        return 1
    fi
    check_api_key
    log_info "starting fusion-health API on ${HOST}:${PORT} ..."
    FUSION_HEALTH_PORT="$PORT" nohup uvicorn fusion_health.api.app:app \
        --host "$HOST" --port "$PORT" \
        >> "$STDOUT_LOG" 2>> "$STDERR_LOG" &
    local pid=$!
    echo "$pid" > "$PID_FILE"
    sleep 2
    if is_running; then
        log_info "fusion-health started (pid $pid, port $PORT)"
    else
        log_error "fusion-health failed to start, see $STDERR_LOG"
        rm -f "$PID_FILE"
        return 1
    fi
}

do_stop() {
    if ! is_running; then
        log_info "fusion-health not running"
        rm -f "$PID_FILE"
        return 0
    fi
    local pid
    pid="$(cat "$PID_FILE")"
    log_info "stopping fusion-health (pid $pid)"
    kill "$pid" 2>/dev/null || true
    for _ in 1 2 3 4 5; do
        kill -0 "$pid" 2>/dev/null || break
        sleep 1
    done
    if kill -0 "$pid" 2>/dev/null; then
        log_error "force kill (pid $pid)"
        kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$PID_FILE"
    log_info "fusion-health stopped"
}

do_status() {
    if is_running; then
        echo "running (pid $(cat "$PID_FILE"), port $PORT)"
        return 0
    fi
    echo "stopped"
    return 1
}

do_doctor() {
    local ok=0
    if is_running; then
        log_info "process: running (pid $(cat "$PID_FILE"), port $PORT)"
    else
        log_error "process: not running"
        ok=1
    fi
    if port_in_use; then
        if is_running; then
            log_info "port ${PORT}: listening"
        else
            log_error "port ${PORT}: in use by another process"
            ok=1
        fi
    else
        if is_running; then
            log_error "port ${PORT}: not listening (process alive but port closed)"
            ok=1
        else
            log_info "port ${PORT}: free"
        fi
    fi
    if [[ -z "${FUSION_HEALTH_API_KEY:-}" ]]; then
        log_warn "API key: unset (localhost-only access)"
    else
        log_info "API key: set"
    fi
    local venv="${FUSION_HEALTH_VENV:-/Users/dahai/fusion/.venv}"
    if [[ -f "${venv}/bin/activate" ]]; then
        log_info "venv: ${venv} (ok)"
    else
        log_error "venv: ${venv} not found"
        ok=1
    fi
    return "$ok"
}

ACTION="${1:-start}"
case "$ACTION" in
    start)  do_start ;;
    stop)   do_stop ;;
    status) do_status ;;
    doctor) do_doctor ;;
    restart) do_stop || true; do_start ;;
    *) echo "usage: $0 {start|stop|status|restart|doctor}" >&2; exit 1 ;;
esac
