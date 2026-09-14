#!/usr/bin/env bash
set -euo pipefail
: "${RECLIP_API_KEY:?Set RECLIP_API_KEY}"
curl --fail-with-body --silent --show-error \
  "${RECLIP_API_BASE_URL:-https://www.reclip.io/api/v1}/tools" \
  -H "Authorization: Bearer ${RECLIP_API_KEY}"
