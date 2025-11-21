# Contributing to Cascade Climate

Thank you for your interest in contributing to Cascade Climate! This document provides guidelines for developers who
want to contribute to this project.

## Development Setup

### Prerequisites

- Python 3.13.2 or later
- Home Assistant 2025.11.2 or later
- [uv](https://github.com/astral-sh/uv) for dependency management (recommended)

### Setting Up Development Environment

```bash
# Clone the repository
git clone https://github.com/vrlo/ha-cascade-climate.git
cd ha-cascade-climate

# Install dependencies
uv sync

# Or with pip
pip install -e .
```

## Architecture Overview

### Control Flow

This integration implements a two-loop cascade controller:

1. **Outer Loop (Primary)**: PI controller that adjusts radiator temperature setpoint based on room temperature error
2. **Inner Loop (Secondary)**: Hysteresis controller that switches pump on/off to maintain radiator temperature
3. **Feedforward Compensation**: Outdoor temperature and weather forecast integration for proactive adjustments
4. **Radiator Energy Observer** : Optional Kalman-like fusion that blends sensor data with pump runtime model to
   compensate for sensor lag

### Event-Driven Architecture

- The integration uses **event-driven architecture** (not polling coordinator)
- State changes on sensor entities trigger `_evaluate_control()` via async callbacks
- 30-second interval timer is only for cache refresh and backup evaluation
- All event handlers use `@callback` decorator for thread safety

### Code Structure

```text
custom_components/cascade_climate/
├── __init__.py           # Integration setup (64 lines)
├── climate.py            # Main climate entity (791 lines)
├── config_flow.py        # UI configuration (318 lines)
├── const.py              # Constants (57 lines)
├── sensor.py             # Companion sensors (149 lines)
├── manifest.json         # Integration metadata
├── strings.json          # UI strings
└── translations/en.json  # English translations
```

### Key Components

**`climate.py`** - Main climate entity and control logic:

- `CascadeClimateConfig`: Dataclass holding all configuration parameters
- `CascadeClimateController`: Pure control logic (PI outer loop, hysteresis inner loop, integral anti-windup)
- `RadiatorEnergyObserver`: Process model and Kalman fusion for radiator temperature estimation
- `CascadeClimateEntity`: ClimateEntity implementation with event subscriptions and service calls

**Key Functions:**

- `CascadeClimateController.compute_radiator_setpoint()`: Outer loop PI controller with anti-windup
- `CascadeClimateController.should_turn_pump_on()`: Inner loop hysteresis controller
- `RadiatorEnergyObserver.update()`: Process model and sensor fusion
- `CascadeClimateEntity._evaluate_control()`: Main control evaluation loop

## Testing

The integration uses pytest with Home Assistant test fixtures.

### Running Tests

```bash
# Run all tests with coverage (recommended)
uv run pytest tests/ \
  --cov=custom_components.cascade_climate \
  --cov-report term-missing \
  -v

# Run specific test file
uv run pytest tests/test_climate.py -v

# Run with durations to identify slow tests
uv run pytest tests/ --durations=10

# Update test snapshots (when intentionally changing entity states/attributes)
uv run pytest tests/ --snapshot-update
# Then re-run without --snapshot-update to verify
```

### Test Structure

- `tests/conftest.py` - Shared fixtures and test configuration
- `tests/test_init.py` - Integration setup and unload tests
- `tests/test_config_flow.py` - Configuration flow tests
- `tests/test_climate.py` - Climate entity and controller logic tests (includes PI integration, hysteresis logic,
  observer modes)
- `tests/test_sensor.py` - Sensor entity tests

### Test Requirements

- **Coverage**: We aim for >95% test coverage
- **Controller Unit Tests** : Test PI integration (error accumulation, anti-windup clamping, integral reset), hysteresis
  logic (pump on/off thresholds, minimum cycle enforcement), and observer modes (runtime-only, sensor-only, fusion
  blending)
- **Integration Tests**: Mock sensor entities and pump switch, verify event subscriptions, verify service calls
- **Snapshot Tests**: Verify entity states and extra attributes

Please include tests with your contributions.

## Code Quality

### Linting

```bash
# Run ruff linter (preferred)
uv run ruff check custom_components/cascade_climate/

# Run mypy type checking
uv run mypy custom_components/cascade_climate/
```

### Code Style

- Follow Home Assistant's [style guidelines](https://developers.home-assistant.io/docs/development_guidelines)
- Use type hints for all function parameters and return values
- Use `@callback` decorator for event handlers
- Document complex algorithms with inline comments
- Keep functions focused and under 50 lines when possible

### Important Notes

- **HACS Custom Component**: This is structured as a custom component, not a core Home Assistant integration
- **No polling required**: Integration is fully event-driven except for 30s cache refresh interval
- **Thread safety**: All sensor event handlers use `@callback` decorator
- **Integral anti-windup**: Integral accumulator clamped when radiator setpoint hits limits or HVAC turns off
- **Service calls**: Pump control via `switch.turn_on`/`switch.turn_off` with `blocking=False`

## Common Development Tasks

### Adding a New Configuration Parameter

1. Add constant to `const.py` (CONF_*, DEFAULT_*)
2. Add field to `CascadeClimateConfig` dataclass in `climate.py`
3. Add parsing logic in `_entry_to_config()` function
4. Add schema field in `config_flow.py` options flow
5. Add translation strings to `strings.json`
6. Update `README.md` with parameter description
7. Add tests for the new parameter

### Modifying Control Logic

1. Update controller methods in `CascadeClimateController` class
2. Add/update unit tests for pure controller logic
3. Update integration tests for end-to-end behavior
4. Add debug logging for new state variables
5. Update extra_state_attributes if exposing new internal state

### Debugging Control Behavior

Enable debug logging in `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.cascade_climate: debug
```

Debug logs include: control evaluation reasons, pump state changes, setpoint calculations, sensor value updates.

Extra state attributes expose: radiator_setpoint, estimated_radiator_temperature, pump_state, observer_mode.

## Submitting Changes

### Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature-name`)
3. Make your changes
4. Add/update tests as needed
5. Run linters and tests locally
6. Commit your changes with clear, descriptive messages
7. Push to your fork and submit a pull request

### Commit Message Guidelines

- Use present tense ("Add feature" not "Added feature")
- Use imperative mood ("Move cursor to..." not "Moves cursor to...")
- First line should be a concise summary (50 chars or less)
- Add detailed explanation in the body if needed

### Pull Request Guidelines

- Include a clear description of the problem and solution
- Reference any related issues
- Include test coverage for new features
- Ensure CI passes before requesting review
- Update documentation if needed

## Reporting Issues

When reporting issues, please include:

- Home Assistant version
- Integration version
- Relevant configuration (sanitized)
- Steps to reproduce
- Expected vs actual behavior
- Relevant logs (enable debug logging as shown above)

## Questions or Need Help?

- Check existing [issues](https://github.com/vrlo/ha-cascade-climate/issues)
- Open a new issue with the question label

## License

By contributing, you agree that your contributions will be licensed under the GPL-3.0 license.
