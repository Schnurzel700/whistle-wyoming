#!/usr/bin/with-contenv bashio

set -euo pipefail

DATA=/data

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

# Whistle class does no per-call telemetry, this covers everything else.
export NEEDLE_TELEMETRY=0
export DO_NOT_TRACK=1

bashio::log.info "starting Whistle STT (default language: ${LANGUAGE}, keywords: ${KEYWORDS:-none}, streaming: ${STREAMING})"
ARGS=(
    --uri tcp://0.0.0.0:10301
    --weights "${DATA}/whistle.cact"
    --default-language "${LANGUAGE}"
    --keywords "${KEYWORDS}"
)
if [[ "${STREAMING}" == "true" ]]; then
    ARGS+=(--streaming)
fi
python /app/server.py "${ARGS[@]}" &
SERVER_PID=$!

bashio::net.wait_for 10301

config=$(bashio::var.json \
    uri "tcp://$(hostname):10301" \
)

if bashio::discovery "wyoming" "${config}" > /dev/null; then
    bashio::log.info "Published Wyoming discovery information"
else
    bashio::log.warning "Failed to publish Wyoming discovery information"
fi

wait "${SERVER_PID}"
