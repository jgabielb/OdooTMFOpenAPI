#!/bin/bash
# TMF/Odoo Integration Test Runner
# Usage: ./run_tests.sh [scenario_number]

export TMF_BASE_URL="${TMF_BASE_URL:-http://localhost:8069}"
export ODOO_DB="${ODOO_DB:-TMF_Odoo_DB}"

cd "$(dirname "$0")"

if [ -n "$1" ]; then
    printf -v padded "%02d" "$1"
    echo "Running scenario $1..."
    python -m pytest -v --tb=short -s "test_${padded}_"*.py
else
    echo "Running ALL scenarios..."
    python -m pytest -v --tb=short
fi
