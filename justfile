default: lint

# Run linting checks
lint:
    uv run --group dev ruff check custom_components/cascade_climate/

# Run type checking
mypy:
    uv run --group dev mypy custom_components/cascade_climate/

# Run all tests with coverage (removes editable install artifacts first)
tests:
    #!/usr/bin/env bash
    rm -f .venv/lib/python3.*/site-packages/__editable__*cascade* 2>/dev/null || true
    PYTHONPATH="$PWD" uv run --no-project pytest tests/ \
      --cov=custom_components.cascade_climate \
      --cov-report term-missing \
      -v

# Run tests with durations
tests-durations:
    #!/usr/bin/env bash
    rm -f .venv/lib/python3.*/site-packages/__editable__*cascade* 2>/dev/null || true
    PYTHONPATH="$PWD" uv run --no-project pytest tests/ \
      --cov=custom_components.cascade_climate \
      --cov-report term-missing \
      --durations=10 \
      -v

# Update test snapshots
snapshots:
    #!/usr/bin/env bash
    rm -f .venv/lib/python3.*/site-packages/__editable__*cascade* 2>/dev/null || true
    PYTHONPATH="$PWD" uv run --no-project pytest tests/ --snapshot-update

# Run tests on changed files only
test-picked:
    #!/usr/bin/env bash
    rm -f .venv/lib/python3.*/site-packages/__editable__*cascade* 2>/dev/null || true
    PYTHONPATH="$PWD" uv run --no-project pytest --picked

# Run specific test file
test-file FILE:
    #!/usr/bin/env bash
    rm -f .venv/lib/python3.*/site-packages/__editable__*cascade* 2>/dev/null || true
    PYTHONPATH="$PWD" uv run --no-project pytest tests/{{FILE}} -v

# Install/sync dependencies
sync:
    uv sync --all-groups

# Clean build artifacts and cache
clean:
    rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
    find . -type d -name __pycache__ -exec rm -rf {} +
