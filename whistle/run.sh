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

if [[ ! -f "${DATA}/whistle.cact" ]]; then
    bashio::log.info "downloading whistle.cact (~17MB)..."
    needle download Cactus-Compute/whistle --out "${DATA}"
fi

bashio::log.info "starting Whistle STT (default language: ${LANGUAGE})"
python /app/server.py \
    --uri tcp://0.0.0.0:10301 \
    --weights "${DATA}/whistle.cact" \
    --default-language "${LANGUAGE}" &
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
