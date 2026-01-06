# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this
repository.

## Overview

This is the **Cascade Climate** integration for Home Assistant - a sophisticated two-loop cascade
controller for heating systems with separate room and radiator temperature control loops.

**Project Status:** HACS-compatible custom component (restructured from Home Assistant core
component layout in commit 454e275). Currently on Home Assistant 2025.11.2, Python 3.13.2+.

**Control Architecture:**

- **Outer Loop (Primary)** : PI controller that adjusts radiator temperature setpoint based on room
  temperature error
- **Inner Loop (Secondary)** : Hysteresis controller that switches pump on/off to maintain radiator
  temperature
- **Feedforward Compensation** : Outdoor temperature and weather forecast integration for proactive
  adjustments
- **Radiator Energy Observer** : Optional Kalman-like fusion that blends sensor data with pump
  runtime model to compensate for sensor lag

## Key Architectural Concepts

### Control Flow

1. Room temperature error drives the outer PI loop → radiator setpoint
2. Radiator energy observer estimates actual radiator temperature (compensating for sensor lag)
3. Inner hysteresis loop compares observer estimate to setpoint → pump on/off decision
4. Minimum cycle duration protection prevents rapid pump cycling

### Event-Driven Updates

- The integration uses **event-driven architecture** (not polling coordinator)
- State changes on sensor entities trigger `_evaluate_control()` via async callbacks
- 30-second interval timer is only for cache refresh and backup evaluation
- All event handlers use `@callback` decorator for thread safety

### State Management

- Controller state ( `_controller` ) tracks: pump state, radiator setpoint, integral accumulator,
  last switch timestamp
- Observer state ( `_energy_observer` ) tracks: estimated radiator temperature, process model state,
  pump activation timestamp
- Entity state (`CascadeClimateEntity`) tracks: cached sensor values, HVAC mode, target temperature

### Observer Modes

- **sensor** (default): Uses radiator sensor directly (legacy behavior)
- **runtime**: Pure process model based on pump runtime with heating/cooling rates
- **fusion**: Kalman-like blend of runtime model and sensor (alpha-weighted average)

## Development Commands

**IMPORTANT:** This is now a HACS custom component. All commands use the `custom_components/`
directory structure, not `homeassistant/components/`.

### Linting

```bash
# Run ruff linter on the integration (preferred method)
ruff check custom_components/cascade_climate/

# Run mypy type checking
mypy custom_components/cascade_climate/

# Or use uv to run with project dependencies
uv run ruff check custom_components/
uv run mypy custom_components/cascade_climate/
```

### Testing

**IMPORTANT:** This project uses `just` recipes for testing to work around an editable install issue
with Home Assistant's component loader. Always use `just` commands instead of calling pytest
directly.

```bash
# Run all tests with coverage (recommended)
just tests

# Run specific test file
just test-file test_climate.py

# Run with durations to identify slow tests
just tests-durations

# Update test snapshots (when intentionally changing entity states/attributes)
just snapshots
# Then re-run with just tests to verify

# Quick test of changed files only
just test-picked
```

**Why not call pytest directly?**

When using `uv sync`, the package is installed in editable mode by default. This creates
`__editable__.cascade_climate-*.finder` artifacts in `site-packages/` that cause Home Assistant's
component loader to fail with `FileNotFoundError` during integration tests. The `just` recipes
handle this by:

1. Removing editable install artifacts before test runs
2. Using `PYTHONPATH="$PWD"` to add the project to the import path
3. Using `uv run --no-project` to avoid re-triggering editable install

If you need to call pytest directly for debugging:

```bash
# Remove editable artifacts first
rm -f .venv/lib/python*/site-packages/__editable__*cascade*

# Run pytest with proper environment
PYTHONPATH="$PWD" uv run --no-project pytest tests/test_climate.py -v
```

### CI/CD

The repository includes GitHub Actions workflows (`.github/workflows/tests.yml`):

- **test**: Matrix testing across Python 3.11, 3.12, 3.13 with coverage reporting
- **lint**: Runs ruff and mypy checks
- **hacs**: Validates HACS compatibility

### Validation

**Note:** Home Assistant's `hassfest`, `translations`, and `gen_requirements_all` scripts are for
core components only and do not apply to custom components.

For HACS validation:

```bash
# HACS validation is run automatically in CI
# Local validation requires HACS action (see .github/workflows/tests.yml)
```

## Code Structure

**Directory Layout:**

```text
custom_components/cascade_climate/  # HACS custom component structure
├── __init__.py                     # Integration setup (64 lines)
├── climate.py                      # Main climate entity (791 lines)
├── config_flow.py                  # UI configuration (318 lines)
├── const.py                        # Constants (57 lines)
├── sensor.py                       # Companion sensors (149 lines)
├── manifest.json                   # Integration metadata
├── strings.json                    # UI strings
└── translations/en.json            # English translations
```

### Core Modules

**`climate.py`** - Main climate entity and control logic (791 lines)

- `CascadeClimateConfig`: Dataclass holding all configuration parameters
- `CascadeClimateController` : Pure control logic (PI outer loop, hysteresis inner loop, integral
  anti-windup)
- `RadiatorEnergyObserver`: Process model and Kalman fusion for radiator temperature estimation
- `CascadeClimateEntity`: ClimateEntity implementation with event subscriptions and service calls

**`const.py`** - Constants and defaults

- Configuration parameter keys (CONF_KP, CONF_KI, CONF_OBSERVER_MODE, etc.)
- Default values for all tunable parameters
- Physical constants (MAX_RADIATOR_TEMP, SUPPLY_WATER_TEMP)
- `ObserverMode` enum

**`config_flow.py`** - UI configuration and options flow

- Initial setup: select room sensor, radiator sensor, pump switch, optional outdoor/forecast
  entities
- Options flow: tune PI gains, hysteresis, observer mode, heating/cooling rates, etc.
- Unique ID based on pump switch entity (prevents duplicate entries)

**`sensor.py`** - Companion sensors

- Radiator setpoint sensor (shows outer loop output)
- Radiator temperature sensor (shows current radiator reading)

**`__init__.py`** - Integration setup

- Validates required entities exist before setup
- Stores runtime config in `entry.runtime_data`
- Forwards setup to climate and sensor platforms

### Key Functions

**`CascadeClimateController.compute_radiator_setpoint()`** - Outer loop PI controller

- Calculates radiator setpoint from room error, integral accumulator, outdoor/forecast compensation
- Includes anti-windup: integral clamped when setpoint hits min/max limits
- Resets integral on HVAC off or target temperature change

**`CascadeClimateController.should_turn_pump_on()`** - Inner loop hysteresis controller

- Compares radiator temperature (from observer) to setpoint ± hysteresis/2
- Enforces minimum cycle duration to prevent pump wear
- Returns `None` when no state change needed

**`RadiatorEnergyObserver.update()`** - Process model and sensor fusion

- Integrates pump runtime: `temp += heating_rate * dt` (with dead time after pump activation)
- Blends prediction with sensor measurement based on observer mode
- Clamps output to valid radiator temperature range

**`CascadeClimateEntity._evaluate_control()`** - Main control evaluation

- Called on sensor state changes and periodic interval
- Runs outer loop → observer → inner loop sequence
- Calls `_set_pump()` to toggle pump via Home Assistant switch service

## Configuration Parameters

### Control Parameters (Outer Loop)

- `proportional_gain` (Kp): Room error → radiator setpoint gain (default: 8.0)
- `integral_gain` (Ki): Integral action strength (default: 0.0 for backward compatibility)
- `base_radiator_temp`: Baseline radiator setpoint with no error (default: 35°C)
- `min_radiator_temp`: Lower limit for radiator setpoint (default: 25°C)

### Control Parameters (Inner Loop)

- `hysteresis`: Temperature band around setpoint for pump switching (default: 1.0°C)
- `min_cycle_duration`: Minimum time between pump state changes (default: 120s)

### Observer Parameters

- `observer_mode`: "sensor" | "runtime" | "fusion" (default: "sensor")
- `heating_rate`: Radiator warm-up rate in °C/s after dead time (default: 0.25)
- `cooling_rate`: Radiator cool-down rate in °C/s (default: 0.05)
- `observer_alpha`: Fusion blend weight toward sensor (default: 0.5)
- `pump_dead_time`: Delay before heating starts after pump activation (default: 5s)

### Compensation Parameters

- `outdoor_gain`: Outdoor temperature → radiator setpoint gain (default: 0.3)
- `outdoor_baseline`: Outdoor temperature below which compensation activates (default: 10°C)

## Testing Considerations

### Test Configuration

The project uses:

- **pytest** with **pytest-asyncio** in AUTO mode for async test execution
- **pytest-homeassistant-custom-component** plugin for Home Assistant fixtures
- **pytest-cov** for coverage reporting
- Configuration in `pyproject.toml` (`[tool.pytest.ini_options]`)

### Known Issues (as of commit 74faf36)

- **Test Status:** 9/30 tests passing
- **pytest-asyncio Compatibility:** Resolved duplicate configuration issue
- **Custom Fixture Override:** `conftest.py` includes async fixture overrides for
  `enable_custom_integrations` and `entity_registry` to fix pytest-asyncio 1.2.0 compatibility
- See `PYTEST_ASYNCIO_SOLUTION.md` for details on the configuration fix

### Controller Unit Tests

- Test PI integration: error accumulation, anti-windup clamping, integral reset
- Test hysteresis logic: pump on/off thresholds, minimum cycle enforcement
- Test observer modes: runtime-only, sensor-only, fusion blending
- These tests run without Home Assistant and should always pass

### Integration Tests

- Mock sensor entities (room, radiator, outdoor) and pump switch
- Verify event subscriptions and state change handling
- Verify service calls to pump switch (turn_on/turn_off)
- Snapshot test entity states and extra attributes
- Use `init_integration` fixture from `conftest.py`

### Config Flow Tests

- Test user step with required entities
- Test options flow for parameter tuning
- Test unique ID enforcement (pump switch)
- Test migration from old config entry versions

## Common Development Tasks

### Adding a New Configuration Parameter

1. Add constant to `const.py` (CONF_*, DEFAULT_*)
2. Add field to `CascadeClimateConfig` dataclass in `climate.py`
3. Add parsing logic in `_entry_to_config()` function
4. Add schema field in `config_flow.py` options flow
5. Add translation strings to `strings.json`
6. Update `README.md` with parameter description

### Modifying Control Logic

1. Update controller methods in `CascadeClimateController` class
2. Add/update unit tests for pure controller logic
3. Update integration tests for end-to-end behavior
4. Add debug logging for new state variables
5. Update extra_state_attributes if exposing new internal state

### Debugging Control Behavior

- Enable debug logging: `custom_components.cascade_climate: debug`
- Debug logs include: control evaluation reasons, pump state changes, setpoint calculations
- Extra state attributes expose: radiator_setpoint, estimated_radiator_temperature, pump_state,
  observer_mode

## Dependencies and Requirements

### Runtime Dependencies

- **Home Assistant:** 2025.11.2 (pinned for testing)
- **Python:** >=3.13.2 (required by Home Assistant 2025.11.2)
- **Production:** No external dependencies (integration only uses Home Assistant core)

### Test Dependencies

- `pytest>=8.0.0` - Test framework
- `pytest-asyncio` - Async test support (version managed by pytest-homeassistant-custom-component)
- `pytest-cov>=4.1.0` - Coverage reporting
- `pytest-homeassistant-custom-component>=0.13.0` - Critical plugin for custom component testing

### Development Tools

- `ruff` - Fast Python linter (preferred over pylint/flake8)
- `mypy` - Static type checking
- `uv` - Fast Python package manager (recommended for dependency management)

## Quality Scale Status

**Current: Bronze** (basic requirements met)

**To reach Silver:**

- Add comprehensive test coverage (>95%)
- Implement entity unavailability handling
- Add reauthentication flow (if applicable)
- Document all configuration parameters
- Add integration owner metadata

See `quality_scale.yaml` for detailed rule status.

## Repository Documentation

Beyond this file, the repository includes:

- **README.md** - User-facing documentation with installation, configuration, and algorithm details
- **RESTRUCTURE_STATUS.md** - Details of the HACS custom component restructuring (commit 454e275)
- **PYTEST_ASYNCIO_SOLUTION.md** - pytest-asyncio 1.2.0 compatibility solution (commit e92910f)
- **TESTING_PLAN.md** - Comprehensive testing strategy
- **REVIEW.md** - Code review with improvement suggestions
- **PLAN.md** - Enhancement plan for PI loop and energy observer
- **quality_scale.yaml** - Home Assistant quality scale tracking

## Important Notes

- **HACS Custom Component:** This is structured as a custom component, not a core Home Assistant
  integration
- **No polling required**: Integration is fully event-driven except for 30s cache refresh interval
- **Thread safety**: All sensor event handlers use `@callback` decorator
- **Integral anti-windup** : Integral accumulator clamped when radiator setpoint hits limits or HVAC
  turns off
- **Observer initialization**: Observer state initialized from radiator sensor on first update
- **Service calls**: Pump control via `switch.turn_on`/`switch.turn_off` with `blocking=False`
- **Config entry reload**: Changing options triggers full reload of config entry
- **Symlinked Files:** Both `CLAUDE.md` and `AGENTS.md` at the repository root are symlinks to
  `.github/copilot-instructions.md`

## Installation

### Manual Installation

```bash
# Copy to Home Assistant config directory
cp -r custom_components/cascade_climate /config/custom_components/
# Restart Home Assistant
```

### HACS Installation (Future)

When published to HACS, users can install directly through the HACS UI as a custom repository.
