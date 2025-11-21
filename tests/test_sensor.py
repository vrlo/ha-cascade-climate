"""Tests for Cascade Climate sensor platform."""

from datetime import timedelta

import pytest

from homeassistant.components.climate import (
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture(name="platforms")
def platforms_sensor() -> list[Platform]:
    """Load both climate and sensor platforms for these tests."""
    return [Platform.CLIMATE, Platform.SENSOR]


async def test_radiator_setpoint_sensor_tracks_climate(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Radiator setpoint sensor should mirror climate attribute."""
    climate_id = "climate.cascade_climate"
    ent_reg = er.async_get(hass)
    sensor_id = ent_reg.async_get_entity_id(
        "sensor",
        "cascade_climate",
        f"{init_integration.entry_id}-radiator-setpoint",
    )
    assert sensor_id is not None

    climate_state = hass.states.get(climate_id)
    sensor_state = hass.states.get(sensor_id)
    assert sensor_state is not None
    assert float(sensor_state.state) == climate_state.attributes["radiator_setpoint"]

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {"entity_id": climate_id, ATTR_TEMPERATURE: 24.0},
        blocking=True,
    )
    await hass.async_block_till_done()

    climate_state = hass.states.get(climate_id)
    sensor_state = hass.states.get(sensor_id)
    assert float(sensor_state.state) == climate_state.attributes["radiator_setpoint"]


async def test_radiator_temperature_sensor_tracks_reading(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Radiator temperature sensor should mirror climate attribute."""
    climate_id = "climate.cascade_climate"
    ent_reg = er.async_get(hass)
    sensor_id = ent_reg.async_get_entity_id(
        "sensor",
        "cascade_climate",
        f"{init_integration.entry_id}-radiator-temperature",
    )
    assert sensor_id is not None

    hass.states.async_set(
        "sensor.radiator_temperature",
        "42.5",
        {"unit_of_measurement": "°C"},
    )
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()

    climate_state = hass.states.get(climate_id)
    sensor_state = hass.states.get(sensor_id)
    assert sensor_state is not None
    assert float(sensor_state.state) == climate_state.attributes["radiator_temperature"]
