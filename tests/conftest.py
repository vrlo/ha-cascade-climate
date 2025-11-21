"""Global test fixtures for cascade_climate."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

# Enable the pytest-homeassistant-custom-component plugin
pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations."""
    yield


@pytest.fixture
async def enable_custom_integrations(hass):
    """Enable custom integrations (async override to fix compatibility)."""
    from homeassistant.loader import DATA_CUSTOM_COMPONENTS
    if DATA_CUSTOM_COMPONENTS in hass.data:
        hass.data.pop(DATA_CUSTOM_COMPONENTS)
    yield


@pytest.fixture
async def entity_registry(hass):
    """Return an empty, loaded, entity registry."""
    from homeassistant.helpers import entity_registry as er
    return er.async_get(hass)


@pytest.fixture
def mock_config_entry():
    """Return the default mocked config entry."""
    from custom_components.cascade_climate.const import (
        ATTR_FORECAST_ENTITY,
        ATTR_OUTSIDE_SENSOR,
        ATTR_PUMP_SWITCH,
        ATTR_RADIATOR_SENSOR,
        ATTR_ROOM_SENSOR,
        CONF_BASE_RADIATOR_TEMP,
        CONF_COOLING_RATE,
        CONF_HYSTERESIS,
        CONF_KI,
        CONF_KP,
        CONF_MIN_CYCLE_DURATION,
        CONF_MIN_RADIATOR_TEMP,
        CONF_OBSERVER_ALPHA,
        CONF_OBSERVER_MODE,
        CONF_PUMP_DEAD_TIME,
        CONF_HEATING_RATE,
        CONF_OUTDOOR_BASELINE,
        CONF_OUTDOOR_GAIN,
        DEFAULT_BASE_RADIATOR_TEMP,
        DEFAULT_COOLING_RATE,
        DEFAULT_HYSTERESIS,
        DEFAULT_KI,
        DEFAULT_KP,
        DEFAULT_MIN_CYCLE_DURATION,
        DEFAULT_MIN_RADIATOR_TEMP,
        DEFAULT_OBSERVER_ALPHA,
        DEFAULT_OBSERVER_MODE,
        DEFAULT_PUMP_DEAD_TIME,
        DEFAULT_HEATING_RATE,
        DEFAULT_OUTDOOR_BASELINE,
        DEFAULT_OUTDOOR_GAIN,
        DOMAIN,
    )

    return MockConfigEntry(
        title="Cascade Climate",
        domain=DOMAIN,
        data={
            ATTR_ROOM_SENSOR: "sensor.room_temperature",
            ATTR_RADIATOR_SENSOR: "sensor.radiator_temperature",
            ATTR_PUMP_SWITCH: "switch.pump",
            ATTR_OUTSIDE_SENSOR: "sensor.outside_temperature",
            ATTR_FORECAST_ENTITY: "weather.home",
            CONF_BASE_RADIATOR_TEMP: DEFAULT_BASE_RADIATOR_TEMP,
            CONF_KP: DEFAULT_KP,
            CONF_KI: DEFAULT_KI,
            CONF_MIN_RADIATOR_TEMP: DEFAULT_MIN_RADIATOR_TEMP,
            CONF_HYSTERESIS: DEFAULT_HYSTERESIS,
            CONF_MIN_CYCLE_DURATION: DEFAULT_MIN_CYCLE_DURATION.total_seconds(),
            CONF_OUTDOOR_GAIN: DEFAULT_OUTDOOR_GAIN,
            CONF_OUTDOOR_BASELINE: DEFAULT_OUTDOOR_BASELINE,
            CONF_OBSERVER_MODE: DEFAULT_OBSERVER_MODE,
            CONF_HEATING_RATE: DEFAULT_HEATING_RATE,
            CONF_COOLING_RATE: DEFAULT_COOLING_RATE,
            CONF_OBSERVER_ALPHA: DEFAULT_OBSERVER_ALPHA,
            CONF_PUMP_DEAD_TIME: DEFAULT_PUMP_DEAD_TIME,
        },
        unique_id="switch.pump",
    )


@pytest.fixture
def platforms():
    """Fixture to specify platforms to test."""
    from homeassistant.const import Platform
    return [Platform.CLIMATE]


@pytest.fixture
async def init_integration(hass, mock_config_entry, platforms):
    """Set up the integration for testing."""
    from unittest.mock import patch

    # Create mock sensor and switch entities
    hass.states.async_set("sensor.room_temperature", "20.0", {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.radiator_temperature", "30.0", {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.outside_temperature", "5.0", {"unit_of_measurement": "°C"})
    hass.states.async_set("switch.pump", "off")
    hass.states.async_set("weather.home", "sunny")

    # Register switch service handlers
    async def mock_turn_on(call):
        """Mock turn on service."""
        entity_id = call.data.get("entity_id")
        if isinstance(entity_id, list):
            for eid in entity_id:
                hass.states.async_set(eid, "on")
        else:
            hass.states.async_set(entity_id, "on")

    async def mock_turn_off(call):
        """Mock turn off service."""
        entity_id = call.data.get("entity_id")
        if isinstance(entity_id, list):
            for eid in entity_id:
                hass.states.async_set(eid, "off")
        else:
            hass.states.async_set(entity_id, "off")

    hass.services.async_register("switch", "turn_on", mock_turn_on)
    hass.services.async_register("switch", "turn_off", mock_turn_off)

    mock_config_entry.add_to_hass(hass)

    with patch("custom_components.cascade_climate.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
