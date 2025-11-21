default: lint

# Run linting checks
lint:
    uv run --group dev ruff check custom_components/cascade_climate/

# Run type checking
mypy:
    uv run --group dev mypy custom_components/cascade_climate/

# Run all tests with coverage
tests:
    uv run --group test pytest tests/ \
      --cov=custom_components.cascade_climate \
      --cov-report term-missing \
      -v

# Run tests with durations
tests-durations:
    uv run --group test pytest tests/ \
      --cov=custom_components.cascade_climate \
      --cov-report term-missing \
      --durations=10 \
      -v

# Update test snapshots
snapshots:
    uv run --group test pytest tests/ --snapshot-update

# Run tests on changed files only
test-picked:
    uv run --group test pytest --picked

# Run specific test file
test-file FILE:
    uv run --group test pytest tests/{{FILE}} -v

# Install/sync dependencies
sync:
    uv sync --all-groups

# Clean build artifacts and cache
clean:
    rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
    find . -type d -name __pycache__ -exec rm -rf {} +
