#!/usr/bin/env bash
# Phone connectivity, option 2 (§11.3): a quick cloudflared tunnel to
# labd's port. --protocol http2 is required on this network — QUIC
# timed out when measured earlier. Prints the hostname as soon as
# cloudflared assigns one, for the QR code / phone pairing link.
set -euo pipefail
PORT="${1:-7700}"
exec cloudflared tunnel --no-autoupdate --protocol http2 --url "http://127.0.0.1:${PORT}"
