#!/usr/bin/with-contenv bashio

set -euo pipefail

DATA=/data

# Telemetry stays off even for the CLI download below.
export NEEDLE_TELEMETRY=0
export DO_NOT_TRACK=1
export HF_HUB_DISABLE_TELEMETRY=1

cleanup() {
    if [[ -n "${SERVER_PID:-}" ]] && kill -0 "${SERVER_PID}" 2>/dev/null; then
        kill "${SERVER_PID}"
        wait "${SERVER_PID}" || true
    fi
}

trap cleanup EXIT SIGINT SIGTERM

LANGUAGE="$(bashio::config 'language')"
KEYWORDS="$(bashio::config 'keywords')"
STREAMING="$(bashio::config 'streaming')"

if [[ ! -f "${DATA}/whistle.cact" ]]; then
    bashio::log.info "downloading whistle.cact (~17MB)..."
    needle download Cactus-Compute/whistle --out "${DATA}"
fi
if [[ ! -f "${DATA}/whistle.cact" ]]; then
    bashio::log.error "whistle.cact missing after download"
    exit 1
fi

bashio::log.info "starting Whistle STT (default language: ${LANGUAGE}, keywords: ${KEYWORDS:-none}, streaming: ${STREAMING})"
ARGS=(
    --uri tcp://0.0.0.0:10301
    --weights "${DATA}/whistle.cact"
    --default-language "${LANGUAGE}"
    --keywords "${KEYWORDS}"
    --lib-cache "${DATA}"
)
if [[ "${STREAMING}" == "true" ]]; then
    ARGS+=(--streaming)
fi
python /app/server.py "${ARGS[@]}" &
SERVER_PID=$!

for _ in $(seq 1 600); do
    if ! kill -0 "${SERVER_PID}" 2>/dev/null; then
        bashio::log.error "server exited during startup"
        exit 1
    fi
    if (exec 3<>"/dev/tcp/127.0.0.1/10301") 2>/dev/null; then
        break
    fi
    sleep 0.5
done

config=$(bashio::var.json \
    uri "tcp://$(hostname):10301" \
)

if bashio::discovery "wyoming" "${config}" > /dev/null; then
    bashio::log.info "Published Wyoming discovery information"
else
    bashio::log.warning "Failed to publish Wyoming discovery information"
fi

wait "${SERVER_PID}"
