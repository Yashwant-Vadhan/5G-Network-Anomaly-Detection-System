#!/usr/bin/env bash
# Helper script to run 5G-NADS multi-stage container locally (T18-007)
set -euo pipefail

IMAGE_NAME="${1:-5gnads-app:latest}"
PORT="${2:-8000}"

echo "Starting 5G-NADS container: ${IMAGE_NAME} on port ${PORT}..."
docker run --rm -it \
  -p "${PORT}:8000" \
  -e NADS_MODE=public \
  -e NADS_ALLOWED_ORIGINS="http://localhost:${PORT},http://127.0.0.1:${PORT}" \
  "${IMAGE_NAME}"
