#!/usr/bin/env bash
# Batch repoint wrong item numbers to canonical items (same tenant + branch).
# Defaults DJANGO_SETTINGS_MODULE to core.settingsprod (production). Override for local dev:
#   export DJANGO_SETTINGS_MODULE=core.settings
# From zentro-backend:
#   SCHEMA=mytenant LOCATION_CODE=MAIN ./scripts/repoint_duplicate_items_batch.sh     # dry-run
#   SCHEMA=mytenant LOCATION_CODE=MAIN ./scripts/repoint_duplicate_items_batch.sh --apply
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${BACKEND}"

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-core.settingsprod}"

PYTHON="${BACKEND}/.venv/bin/python"
if [[ ! -x "${PYTHON}" ]]; then PYTHON="python3"; fi

SCHEMA="${SCHEMA:-primewise}"
LOCATION_CODE="${LOCATION_CODE:-MWANJARI}"
APPLY_FLAG=()
if [[ "${1:-}" == "--apply" ]]; then APPLY_FLAG=(--apply); fi

echo "DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE}"
echo "Schema=${SCHEMA}  Location=${LOCATION_CODE}  apply=${APPLY_FLAG[*]:-dry-run only}"

pairs=(
  "ITM-000829:ITM-000145"
  "ITM-000836:ITM-000402"
  "ITM-000844:ITM-000565"
  "ITM-000854:ITM-000689"
  "ITM-000848:ITM-000620"
  "ITM-000853:ITM-000667"
  "ITM-000838:ITM-000250"
  "ITM-000826:ITM-000050"
  "ITM-000832:ITM-000218"
  "ITM-000835:ITM-000377"
  "ITM-000857:ITM-000858"
)

ok=0
skipped=0
failed=0

for entry in "${pairs[@]}"; do
  IFS=: read -r from to <<<"${entry}"
  echo ""
  echo "=== ${from} -> ${to} ==="
  set +e
  output=$("${PYTHON}" manage.py repoint_item_ledger_item \
    --schema="${SCHEMA}" \
    --from-item-no="${from}" \
    --to-item-no="${to}" \
    --location-code="${LOCATION_CODE}" \
    "${APPLY_FLAG[@]}" 2>&1)
  rc=$?
  set -e
  echo "${output}"
  if (( rc != 0 )); then
    if [[ "${output}" == *"not found."* ]]; then
      echo "SKIP: item not found — continuing."
      ((skipped++)) || true
      continue
    fi
    ((failed++)) || true
    echo "ERROR: repoint failed (exit ${rc}). Stopping batch."
    exit "${rc}"
  fi
  ((ok++)) || true
done

echo ""
echo "Batch done: ${ok} ok, ${skipped} skipped (not found), ${failed} failed, ${#pairs[@]} total."
