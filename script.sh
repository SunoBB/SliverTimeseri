#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$ROOT_DIR/.venv/bin/python"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [[ -x "$VENV_PYTHON" ]]; then
  PYTHON_BIN="$VENV_PYTHON"
fi

run_cli() {
  PYTHONPATH="$ROOT_DIR/backend/src" "$PYTHON_BIN" -m silver_timeseri.cli "$@"
}

show_help() {
  cat <<'EOF'
Backend helper script

Usage:
  ./script.sh help
  ./script.sh install
  ./script.sh db-up
  ./script.sh db-down
  ./script.sh db-status
  ./script.sh api
  ./script.sh summary [raw|curated] [start_date] [end_date]
  ./script.sh export-csv [raw|curated] [output.csv] [start_date] [end_date]
  ./script.sh export-xlsx [raw|curated] [output.xlsx] [start_date] [end_date]
  ./script.sh sync [start_date] [end_date]
  ./script.sh test

Examples:
  ./script.sh install
  ./script.sh db-up
  ./script.sh api
  ./script.sh summary curated 2020-01-01 2026-04-05
  ./script.sh export-csv curated data/silver_curated.csv 2020-01-01 2026-04-05
  ./script.sh export-xlsx raw data/silver_raw.xlsx 2020-01-01 2026-04-05
  ./script.sh sync 2020-01-01 2026-04-05
  ./script.sh test

Notes:
  - Default series layer is: curated
  - Default date range is: 2011-01-01 to 2026-04-11
  - Export .xlsx requires openpyxl in .venv
EOF
}

default_layer() {
  echo "${1:-curated}"
}

default_start() {
  echo "${1:-2020-01-01}"
}

default_end() {
  echo "${1:-2026-04-05}"
}

command="${1:-help}"
shift || true

case "$command" in
  help|-h|--help)
    show_help
    ;;
  install)
    "$ROOT_DIR/.venv/bin/pip" install -r "$ROOT_DIR/backend/requirements.txt"
    ;;
  db-up)
    (cd "$ROOT_DIR/backend" && docker compose up -d)
    ;;
  db-down)
    (cd "$ROOT_DIR/backend" && docker compose down)
    ;;
  db-status)
    (cd "$ROOT_DIR/backend" && docker compose ps)
    ;;
  api)
    PYTHONPATH="$ROOT_DIR/backend/src" "$PYTHON_BIN" -m uvicorn silver_timeseri.api:app --host 127.0.0.1 --port 8000 --reload
    ;;
  summary)
    layer="$(default_layer "${1:-}")"
    start_date="$(default_start "${2:-}")"
    end_date="$(default_end "${3:-}")"
    run_cli summarize --series-layer "$layer" --start-date "$start_date" --end-date "$end_date" --timeframe 1d
    ;;
  export-csv)
    layer="$(default_layer "${1:-}")"
    output="${2:-data/silver_${layer}.csv}"
    start_date="$(default_start "${3:-}")"
    end_date="$(default_end "${4:-}")"
    run_cli export --series-layer "$layer" --start-date "$start_date" --end-date "$end_date" --timeframe 1d --output "$output"
    ;;
  export-xlsx)
    layer="$(default_layer "${1:-}")"
    output="${2:-data/silver_${layer}.xlsx}"
    start_date="$(default_start "${3:-}")"
    end_date="$(default_end "${4:-}")"
    run_cli export --series-layer "$layer" --start-date "$start_date" --end-date "$end_date" --timeframe 1d --output "$output"
    ;;
  sync)
    start_date="$(default_start "${1:-}")"
    end_date="$(default_end "${2:-}")"
    run_cli sync-db --start-date "$start_date" --end-date "$end_date" --timeframe 1d
    ;;
  test)
    PYTHONPATH="$ROOT_DIR/backend/src" "$PYTHON_BIN" -m unittest discover -s "$ROOT_DIR/backend/tests"
    ;;
  *)
    echo "Unknown command: $command" >&2
    echo >&2
    show_help
    exit 1
    ;;
esac
