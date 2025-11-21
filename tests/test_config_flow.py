"""Test the Cascade Climate config flow."""

from unittest.mock import patch

import pytest

from custom_components.cascade_climate.const import (
    ATTR_FORECAST_ENTITY,
    ATTR_OUTSIDE_SENSOR,
    ATTR_PUMP_SWITCH,
    ATTR_RADIATOR_SENSOR,
    ATTR_ROOM_SENSOR,
    CONF_BASE_RADIATOR_TEMP,
    CONF_COOLING_RATE,
    CONF_HEATING_RATE,
    CONF_HYSTERESIS,
    CONF_KI,
    CONF_KP,
    CONF_MIN_CYCLE_DURATION,
    CONF_MIN_RADIATOR_TEMP,
    CONF_OBSERVER_ALPHA,
    CONF_OBSERVER_MODE,
    CONF_OUTDOOR_BASELINE,
    CONF_OUTDOOR_GAIN,
    CONF_PUMP_DEAD_TIME,
    DEFAULT_BASE_RADIATOR_TEMP,
    DEFAULT_COOLING_RATE,
    DEFAULT_HEATING_RATE,
    DEFAULT_HYSTERESIS,
    DEFAULT_KI,
    DEFAULT_KP,
    DEFAULT_MIN_CYCLE_DURATION,
    DEFAULT_MIN_RADIATOR_TEMP,
    DEFAULT_OBSERVER_ALPHA,
    DEFAULT_OUTDOOR_BASELINE,
    DEFAULT_OUTDOOR_GAIN,
    DEFAULT_PUMP_DEAD_TIME,
    DOMAIN,
    ObserverMode,
)

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant import config_entries
from pytest_homeassistant_custom_component.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.cascade_climate.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "Test Cascade",
                ATTR_ROOM_SENSOR: "sensor.room_temp",
                ATTR_RADIATOR_SENSOR: "sensor.radiator_temp",
                ATTR_PUMP_SWITCH: "switch.pump",
                ATTR_OUTSIDE_SENSOR: "sensor.outside_temp",
                ATTR_FORECAST_ENTITY: "weather.home",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Test Cascade"
    assert result2["data"] == {
        ATTR_ROOM_SENSOR: "sensor.room_temp",
        ATTR_RADIATOR_SENSOR: "sensor.radiator_temp",
        ATTR_PUMP_SWITCH: "switch.pump",
        ATTR_OUTSIDE_SENSOR: "sensor.outside_temp",
        ATTR_FORECAST_ENTITY: "weather.home",
        CONF_BASE_RADIATOR_TEMP: DEFAULT_BASE_RADIATOR_TEMP,
        CONF_KP: DEFAULT_KP,
        CONF_KI: DEFAULT_KI,
        CONF_MIN_RADIATOR_TEMP: DEFAULT_MIN_RADIATOR_TEMP,
        CONF_HYSTERESIS: DEFAULT_HYSTERESIS,
        CONF_MIN_CYCLE_DURATION: DEFAULT_MIN_CYCLE_DURATION.total_seconds(),
        CONF_OUTDOOR_GAIN: DEFAULT_OUTDOOR_GAIN,
        CONF_OUTDOOR_BASELINE: DEFAULT_OUTDOOR_BASELINE,
        CONF_OBSERVER_MODE: ObserverMode.SENSOR.value,
        CONF_HEATING_RATE: DEFAULT_HEATING_RATE,
        CONF_COOLING_RATE: DEFAULT_COOLING_RATE,
        CONF_OBSERVER_ALPHA: DEFAULT_OBSERVER_ALPHA,
        CONF_PUMP_DEAD_TIME: DEFAULT_PUMP_DEAD_TIME,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_no_optional_sensors(hass: HomeAssistant) -> None:
    """Test form without optional sensors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.cascade_climate.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "Test Cascade",
                ATTR_ROOM_SENSOR: "sensor.room_temp",
                ATTR_RADIATOR_SENSOR: "sensor.radiator_temp",
                ATTR_PUMP_SWITCH: "switch.pump",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Test Cascade"
    assert ATTR_OUTSIDE_SENSOR not in result2["data"] or result2["data"][ATTR_OUTSIDE_SENSOR] is None
    assert ATTR_FORECAST_ENTITY not in result2["data"] or result2["data"][ATTR_FORECAST_ENTITY] is None
    assert len(mock_setup_entry.mock_calls) == 1


async def test_duplicate_entry(hass: HomeAssistant) -> None:
    """Test that duplicate entries are prevented."""
    # Create existing entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="switch.pump",
        data={
            ATTR_ROOM_SENSOR: "sensor.room_temp",
            ATTR_RADIATOR_SENSOR: "sensor.radiator_temp",
            ATTR_PUMP_SWITCH: "switch.pump",
        },
    )
    entry.add_to_hass(hass)

    # Try to create duplicate
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Test Cascade 2",
            ATTR_ROOM_SENSOR: "sensor.other_room_temp",
            ATTR_RADIATOR_SENSOR: "sensor.other_radiator_temp",
            ATTR_PUMP_SWITCH: "switch.pump",  # Same pump - should abort
        },
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test options flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="switch.pump",
        data={
            ATTR_ROOM_SENSOR: "sensor.room_temp",
            ATTR_RADIATOR_SENSOR: "sensor.radiator_temp",
            ATTR_PUMP_SWITCH: "switch.pump",
            CONF_BASE_RADIATOR_TEMP: 35.0,
            CONF_KP: 8.0,
        },
    )
    entry.add_to_hass(hass)

    # Initialize options flow
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    # Update options
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            ATTR_OUTSIDE_SENSOR: "sensor.new_outside_temp",
            ATTR_FORECAST_ENTITY: "weather.forecast",
            CONF_BASE_RADIATOR_TEMP: 40.0,
            CONF_KP: 10.0,
            CONF_KI: 0.25,
            CONF_MIN_RADIATOR_TEMP: 28.0,
            CONF_HYSTERESIS: 1.5,
            CONF_MIN_CYCLE_DURATION: 180,
            CONF_OUTDOOR_GAIN: 0.5,
            CONF_OUTDOOR_BASELINE: 12.0,
            CONF_OBSERVER_MODE: ObserverMode.FUSION.value,
            CONF_HEATING_RATE: 0.3,
            CONF_COOLING_RATE: 0.07,
            CONF_OBSERVER_ALPHA: 0.7,
            CONF_PUMP_DEAD_TIME: 8,
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == {
        ATTR_OUTSIDE_SENSOR: "sensor.new_outside_temp",
        ATTR_FORECAST_ENTITY: "weather.forecast",
        CONF_BASE_RADIATOR_TEMP: 40.0,
        CONF_KP: 10.0,
        CONF_KI: 0.25,
        CONF_MIN_RADIATOR_TEMP: 28.0,
        CONF_HYSTERESIS: 1.5,
        CONF_MIN_CYCLE_DURATION: 180,
        CONF_OUTDOOR_GAIN: 0.5,
        CONF_OUTDOOR_BASELINE: 12.0,
        CONF_OBSERVER_MODE: ObserverMode.FUSION.value,
        CONF_HEATING_RATE: 0.3,
        CONF_COOLING_RATE: 0.07,
        CONF_OBSERVER_ALPHA: 0.7,
        CONF_PUMP_DEAD_TIME: 8,
    }
