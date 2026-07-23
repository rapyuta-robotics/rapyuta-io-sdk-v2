# Local quality checks mirroring .github/workflows/quality-checks.yml
# Run `just` or `just check` for a full local quality gate.

python_version := "3.10"

# Default: run all checks
default: check

# Run all quality checks (lint + smoke + tests)
check: lint smoke test

# Lint with ruff
lint:
    uvx ruff check

# Format with ruff
format:
    uvx ruff format

# Lint + format fix in one step
fix:
    uvx ruff check --fix
    uvx ruff format

# Smoke-test SDK imports
smoke:
    uv run --python {{python_version}} python -c 'import rapyuta_io_sdk_v2; from rapyuta_io_sdk_v2 import Client, AsyncClient; from rapyuta_io_sdk_v2.pydantic_source.source import ConfigTreeSource; print("smoke imports OK")'

# Run full test suite with coverage
test:
    uv run --python {{python_version}} pytest tests/ --cov

# Run tests for a specific file (usage: just test-file tests/sync_tests/test_project.py)
test-file file:
    uv run --python {{python_version}} pytest {{file}} -v

# Sync dependencies
sync:
    uv sync --python {{python_version}} --all-extras --dev

# Build the package
build:
    uv build

# Check compatibility across all supported Python versions (3.8–3.13)
compat:
    #!/usr/bin/env bash
    set -e
    versions="3.8 3.9 3.10 3.11 3.12 3.13"
    failed=""
    for v in $versions; do
        echo "=== Python $v ==="
        if uv run --python $v python -c 'import rapyuta_io_sdk_v2; from rapyuta_io_sdk_v2 import Client, AsyncClient; from rapyuta_io_sdk_v2.pydantic_source.source import ConfigTreeSource; print("  smoke OK")' && \
           uv run --python $v pytest tests/ -q --no-header 2>&1 | tail -1; then
            echo "  PASS"
        else
            echo "  FAIL"
            failed="$failed $v"
        fi
    done
    echo ""
    if [ -n "$failed" ]; then
        echo "FAILED on:$failed"
        exit 1
    else
        echo "All versions passed."
    fi
