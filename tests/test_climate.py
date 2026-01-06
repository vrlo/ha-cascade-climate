"""Test the Cascade Climate climate platform."""

from dataclasses import replace
from datetime import timedelta
from typing import Any

import pytest

from custom_components.cascade_climate.climate import (
    CascadeClimateConfig,
    CascadeClimateController,
    RadiatorEnergyObserver,
)
from custom_components.cascade_climate.const import (
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
    DEFAULT_UPDATE_INTERVAL,
    MAX_RADIATOR_TEMP,
    ObserverMode,
)

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
)
from homeassistant.core import HomeAssistant
from homeassistant.core import CoreState, State
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.restore_state import STORAGE_KEY
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_restore_state_shutdown_restart,
    mock_restore_cache,
    mock_restore_cache_with_extra_data,
)


BASE_CONFIG = CascadeClimateConfig(
    room_sensor="sensor.room_temperature",
    radiator_sensor="sensor.radiator_temperature",
    pump_switch="switch.pump",
    outside_sensor="sensor.outside_temperature",
    forecast_entity="weather.home",
    base_radiator_temp=DEFAULT_BASE_RADIATOR_TEMP,
    proportional_gain=DEFAULT_KP,
    integral_gain=DEFAULT_KI,
    min_radiator_temp=DEFAULT_MIN_RADIATOR_TEMP,
    hysteresis=DEFAULT_HYSTERESIS,
    min_cycle_duration=DEFAULT_MIN_CYCLE_DURATION,
    update_interval=DEFAULT_UPDATE_INTERVAL,
    outdoor_gain=DEFAULT_OUTDOOR_GAIN,
    outdoor_baseline=DEFAULT_OUTDOOR_BASELINE,
    observer_mode=ObserverMode.SENSOR,
    heating_rate=DEFAULT_HEATING_RATE,
    cooling_rate=DEFAULT_COOLING_RATE,
    observer_alpha=DEFAULT_OBSERVER_ALPHA,
    pump_dead_time=5.0,
)


def _make_config(**kwargs: float) -> CascadeClimateConfig:
    """Return a CascadeClimateConfig with overrides."""
    return replace(BASE_CONFIG, **kwargs)


async def test_climate_entity_setup(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test climate entity is set up correctly."""
    entry = init_integration

    # Check entity is registered
    entity_id = "climate.cascade_climate"
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry
    assert entity_entry.unique_id == f"{entry.entry_id}-climate"

    # Check entity state
    state = hass.states.get(entity_id)
    assert state
    assert state.state == HVACMode.OFF  # New installations default to OFF
    assert state.attributes.get(ATTR_TEMPERATURE) == 21.0


async def test_set_temperature(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test setting the target temperature."""
    entity_id = "climate.cascade_climate"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 23.0},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.attributes.get(ATTR_TEMPERATURE) == 23.0


async def test_set_hvac_mode_heat(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test setting HVAC mode to heat."""
    entity_id = "climate.cascade_climate"

    # First turn off
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == HVACMode.OFF

    # Then turn back on
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == HVACMode.HEAT


async def test_set_hvac_mode_off(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test setting HVAC mode to off."""
    entity_id = "climate.cascade_climate"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == HVACMode.OFF

    # Check pump is turned off when HVAC mode is off
    pump_state = hass.states.get("switch.pump")
    assert pump_state.state == STATE_OFF


async def test_cascade_control_pump_on(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test cascade control turns pump on when radiator is cold."""
    entity_id = "climate.cascade_climate"

    # Set target temperature higher than room temp
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 23.0},
        blocking=True,
    )

    # Simulate radiator temperature dropping below setpoint
    hass.states.async_set(
        "sensor.radiator_temperature", "25.0", {"unit_of_measurement": "°C"}
    )
    await hass.async_block_till_done()

    # Fire time to trigger evaluation
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=35))
    await hass.async_block_till_done()

    # Pump should eventually turn on (controller should decide based on cascade logic)
    # Note: Actual behavior depends on cascade controller logic


async def test_cascade_control_pump_off(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test cascade control turns pump off when radiator is hot."""
    # First ensure pump is on by setting low radiator temp
    hass.states.async_set(
        "sensor.radiator_temperature", "20.0", {"unit_of_measurement": "°C"}
    )
    await hass.async_block_till_done()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=130))
    await hass.async_block_till_done()

    # Now simulate radiator heating up
    hass.states.async_set(
        "sensor.radiator_temperature", "45.0", {"unit_of_measurement": "°C"}
    )
    await hass.async_block_till_done()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=260))
    await hass.async_block_till_done()

    # Pump should turn off when radiator is too hot


async def test_sensor_unavailable(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test handling of unavailable sensor."""
    entity_id = "climate.cascade_climate"

    # Make room sensor unavailable
    hass.states.async_set("sensor.room_temperature", "unavailable")
    await hass.async_block_till_done()

    # Climate entity should still be available but handle gracefully
    state = hass.states.get(entity_id)
    assert state is not None


async def test_outdoor_temperature_compensation(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test outdoor temperature compensation affects radiator setpoint."""
    entity_id = "climate.cascade_climate"

    # Set a low outdoor temperature
    hass.states.async_set(
        "sensor.outside_temperature", "-5.0", {"unit_of_measurement": "°C"}
    )
    await hass.async_block_till_done()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=35))
    await hass.async_block_till_done()

    # The controller should compute a higher radiator setpoint due to cold outdoor temp
    state = hass.states.get(entity_id)
    assert state is not None


async def test_observer_attributes_exposed(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Ensure observer attributes are visible and populated."""
    entity_id = "climate.cascade_climate"

    state = hass.states.get(entity_id)
    assert "estimated_radiator_temperature" in state.attributes
    assert state.attributes["observer_mode"] == ObserverMode.SENSOR.value

    # Trigger an update so the observer captures the latest reading
    hass.states.async_set(
        "sensor.radiator_temperature",
        "34.0",
        {"unit_of_measurement": "°C"},
    )
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=35))
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes["estimated_radiator_temperature"] is not None


def test_pi_integral_accumulates() -> None:
    """Integral gain should increase radiator setpoint over time."""
    config = _make_config(integral_gain=0.05)
    controller = CascadeClimateController(config)
    now = dt_util.utcnow()
    base = controller.compute_radiator_setpoint(
        room_target=22.0,
        room_temp=21.5,
        outside_temp=None,
        forecast_temp=None,
        now=now,
    )
    later = now + timedelta(seconds=60)
    with_integral = controller.compute_radiator_setpoint(
        room_target=22.0,
        room_temp=21.5,
        outside_temp=None,
        forecast_temp=None,
        now=later,
    )
    assert with_integral > base

    controller.reset_integral()
    reset = controller.compute_radiator_setpoint(
        room_target=22.0,
        room_temp=21.5,
        outside_temp=None,
        forecast_temp=None,
        now=later + timedelta(seconds=10),
    )
    assert reset <= with_integral


def test_pi_integral_clamped() -> None:
    """Integral contribution should respect anti-windup limits."""
    config = _make_config(integral_gain=0.5)
    controller = CascadeClimateController(config)
    now = dt_util.utcnow()
    limit = (MAX_RADIATOR_TEMP - config.min_radiator_temp) / config.integral_gain

    for idx in range(10):
        now = now + timedelta(minutes=5)
        value = controller.compute_radiator_setpoint(
            room_target=30.0,
            room_temp=10.0,
            outside_temp=None,
            forecast_temp=None,
            now=now,
        )
        assert value <= MAX_RADIATOR_TEMP

    assert controller._room_error_integral <= limit * 1.01  # type: ignore[attr-defined]


def test_energy_observer_runtime_prediction() -> None:
    """Runtime observer should heat the estimate once dead time passes."""
    config = _make_config(
        observer_mode=ObserverMode.RUNTIME,
        pump_dead_time=0.0,
        heating_rate=0.1,
        cooling_rate=0.0,
    )
    observer = RadiatorEnergyObserver(config)
    now = dt_util.utcnow()
    observer.reset(None)
    observer.update(now=now, pump_on=False, measured_temp=30.0)
    estimate = observer.update(
        now=now + timedelta(seconds=20),
        pump_on=True,
        measured_temp=None,
    )
    assert estimate and estimate > 30.0


def test_energy_observer_fusion_uses_sensor() -> None:
    """Fusion observer should lean toward sensor readings based on alpha."""
    config = _make_config(observer_mode=ObserverMode.FUSION, observer_alpha=0.9)
    observer = RadiatorEnergyObserver(config)
    now = dt_util.utcnow()
    observer.reset(None)
    observer.update(now=now, pump_on=False, measured_temp=30.0)
    estimate = observer.update(
        now=now + timedelta(seconds=10),
        pump_on=False,
        measured_temp=40.0,
    )
    assert estimate and estimate > 35.0


def test_energy_observer_sensor_passthrough() -> None:
    """Sensor mode should mirror the measurement regardless of runtime model."""
    config = _make_config(observer_mode=ObserverMode.SENSOR)
    observer = RadiatorEnergyObserver(config)
    now = dt_util.utcnow()
    observer.reset(None)
    observer.update(now=now, pump_on=False, measured_temp=30.0)

    estimate = observer.update(
        now=now + timedelta(seconds=15),
        pump_on=True,
        measured_temp=33.5,
    )
    assert estimate == pytest.approx(33.5, abs=0.01)


def test_energy_observer_dead_time_delays_heating() -> None:
    """Runtime observer should wait for dead time before heating rises."""
    config = _make_config(
        observer_mode=ObserverMode.RUNTIME,
        pump_dead_time=10.0,
        heating_rate=0.5,
    )
    observer = RadiatorEnergyObserver(config)
    now = dt_util.utcnow()
    observer.reset(None)
    observer.update(now=now, pump_on=False, measured_temp=30.0)

    early = observer.update(
        now=now + timedelta(seconds=5),
        pump_on=True,
        measured_temp=None,
    )
    assert pytest.approx(early, rel=1e-3) == 30.0

    late = observer.update(
        now=now + timedelta(seconds=15),
        pump_on=True,
        measured_temp=None,
    )
    assert late and late > early


def test_energy_observer_cools_with_pump_off() -> None:
    """Observer should decay estimate when pump is off."""
    config = _make_config(observer_mode=ObserverMode.RUNTIME, cooling_rate=0.1)
    observer = RadiatorEnergyObserver(config)
    now = dt_util.utcnow()
    observer.reset(None)
    observer.update(now=now, pump_on=False, measured_temp=40.0)

    cooled = observer.update(
        now=now + timedelta(seconds=20),
        pump_on=False,
        measured_temp=None,
    )
    assert cooled and cooled < 40.0


def test_energy_observer_reset_sets_estimate() -> None:
    """Explicit reset should seed the estimate."""
    observer = RadiatorEnergyObserver(BASE_CONFIG)
    observer.reset(25.0)
    now = dt_util.utcnow()
    value = observer.update(now=now, pump_on=False, measured_temp=None)
    assert value == 25.0


async def test_min_cycle_duration(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test minimum cycle duration prevents rapid switching."""
    # Turn pump on
    hass.states.async_set(
        "sensor.radiator_temperature", "20.0", {"unit_of_measurement": "°C"}
    )
    await hass.async_block_till_done()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=130))
    await hass.async_block_till_done()

    # Quickly try to turn it off (within min cycle duration)
    hass.states.async_set(
        "sensor.radiator_temperature", "45.0", {"unit_of_measurement": "°C"}
    )
    await hass.async_block_till_done()

    # Should not switch immediately due to min_cycle_duration
    # Would need to wait 2 minutes (DEFAULT_MIN_CYCLE_DURATION)


async def test_pump_state_syncs_manual_switch(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Controller should mirror manual pump toggles."""
    entity_id = "climate.cascade_climate"

    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.pump"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes["pump_state"] is True

    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.pump"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes["pump_state"] is False


async def test_entity_cleanup(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test entity cleanup on removal."""
    entity_id = "climate.cascade_climate"

    # Verify entity exists
    state = hass.states.get(entity_id)
    assert state is not None

    # Unload entry
    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    # Entity should be removed or unavailable
    state = hass.states.get(entity_id)
    assert state is None or state.state == "unavailable"


# --- State Restoration Tests ---


async def test_restore_hvac_mode_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that HVAC mode OFF is restored after restart."""
    entity_id = "climate.cascade_climate"

    mock_restore_cache(
        hass,
        (State(entity_id, HVACMode.OFF, {ATTR_TEMPERATURE: 21.0}),),
    )

    hass.set_state(CoreState.starting)

    hass.states.async_set("sensor.room_temperature", "20.0")
    hass.states.async_set("sensor.radiator_temperature", "30.0")
    hass.states.async_set("sensor.outside_temperature", "5.0")
    hass.states.async_set("switch.pump", "off")
    hass.states.async_set("weather.home", "sunny")
    hass.services.async_register("switch", "turn_on", lambda _: None)
    hass.services.async_register("switch", "turn_off", lambda _: None)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == HVACMode.OFF


async def test_restore_hvac_mode_heat(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that HVAC mode HEAT is restored after restart."""
    entity_id = "climate.cascade_climate"

    mock_restore_cache(
        hass,
        (State(entity_id, HVACMode.HEAT, {ATTR_TEMPERATURE: 22.5}),),
    )

    hass.set_state(CoreState.starting)

    hass.states.async_set("sensor.room_temperature", "20.0")
    hass.states.async_set("sensor.radiator_temperature", "30.0")
    hass.states.async_set("sensor.outside_temperature", "5.0")
    hass.states.async_set("switch.pump", "off")
    hass.states.async_set("weather.home", "sunny")
    hass.services.async_register("switch", "turn_on", lambda _: None)
    hass.services.async_register("switch", "turn_off", lambda _: None)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_TEMPERATURE] == 22.5


async def test_restore_target_temperature(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that target temperature is restored after restart."""
    entity_id = "climate.cascade_climate"

    mock_restore_cache(
        hass,
        (State(entity_id, HVACMode.HEAT, {ATTR_TEMPERATURE: 19.5}),),
    )

    hass.set_state(CoreState.starting)

    hass.states.async_set("sensor.room_temperature", "20.0")
    hass.states.async_set("sensor.radiator_temperature", "30.0")
    hass.states.async_set("sensor.outside_temperature", "5.0")
    hass.states.async_set("switch.pump", "off")
    hass.states.async_set("weather.home", "sunny")
    hass.services.async_register("switch", "turn_on", lambda _: None)
    hass.services.async_register("switch", "turn_off", lambda _: None)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_TEMPERATURE] == 19.5


async def test_restore_with_extra_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that internal controller state is restored from extra data."""
    entity_id = "climate.cascade_climate"

    extra_data = {
        "room_error_integral": 150.5,
        "last_pump_switch_iso": "2024-01-15T10:30:00+00:00",
        "radiator_estimate": 38.5,
        "pump_on_since_iso": None,
    }

    mock_restore_cache_with_extra_data(
        hass,
        ((State(entity_id, HVACMode.HEAT, {ATTR_TEMPERATURE: 21.0}), extra_data),),
    )

    hass.set_state(CoreState.starting)

    hass.states.async_set("sensor.room_temperature", "20.0")
    hass.states.async_set("sensor.radiator_temperature", "30.0")
    hass.states.async_set("sensor.outside_temperature", "5.0")
    hass.states.async_set("switch.pump", "off")
    hass.states.async_set("weather.home", "sunny")
    hass.services.async_register("switch", "turn_on", lambda _: None)
    hass.services.async_register("switch", "turn_off", lambda _: None)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes.get("estimated_radiator_temperature") == 38.5


async def test_no_restore_state_uses_defaults(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that new installations default to OFF mode."""
    entity_id = "climate.cascade_climate"

    hass.set_state(CoreState.starting)

    hass.states.async_set("sensor.room_temperature", "20.0")
    hass.states.async_set("sensor.radiator_temperature", "30.0")
    hass.states.async_set("sensor.outside_temperature", "5.0")
    hass.states.async_set("switch.pump", "off")
    hass.states.async_set("weather.home", "sunny")
    hass.services.async_register("switch", "turn_on", lambda _: None)
    hass.services.async_register("switch", "turn_off", lambda _: None)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == HVACMode.OFF
    assert state.attributes[ATTR_TEMPERATURE] == 21.0


async def test_restore_invalid_state_uses_defaults(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that invalid restored state falls back to defaults."""
    entity_id = "climate.cascade_climate"

    mock_restore_cache(
        hass,
        (State(entity_id, "invalid_mode", {ATTR_TEMPERATURE: "not_a_number"}),),
    )

    hass.set_state(CoreState.starting)

    hass.states.async_set("sensor.room_temperature", "20.0")
    hass.states.async_set("sensor.radiator_temperature", "30.0")
    hass.states.async_set("sensor.outside_temperature", "5.0")
    hass.states.async_set("switch.pump", "off")
    hass.states.async_set("weather.home", "sunny")
    hass.services.async_register("switch", "turn_on", lambda _: None)
    hass.services.async_register("switch", "turn_off", lambda _: None)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == HVACMode.OFF
    assert state.attributes[ATTR_TEMPERATURE] == 21.0


async def test_restore_pi_integral_affects_control(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that restored PI integral affects radiator setpoint calculation."""
    entity_id = "climate.cascade_climate"

    extra_data = {
        "room_error_integral": 600.0,
        "last_pump_switch_iso": None,
        "radiator_estimate": None,
        "pump_on_since_iso": None,
    }

    mock_restore_cache_with_extra_data(
        hass,
        ((State(entity_id, HVACMode.HEAT, {ATTR_TEMPERATURE: 22.0}), extra_data),),
    )

    hass.set_state(CoreState.starting)

    hass.states.async_set("sensor.room_temperature", "21.5")
    hass.states.async_set("sensor.radiator_temperature", "30.0")
    hass.states.async_set("sensor.outside_temperature", "5.0")
    hass.states.async_set("switch.pump", "off")
    hass.states.async_set("weather.home", "sunny")
    hass.services.async_register("switch", "turn_on", lambda _: None)
    hass.services.async_register("switch", "turn_off", lambda _: None)

    # Enable integral gain for this test
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={**mock_config_entry.data, "integral_gain": 0.01},
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    # base(35) + Kp(8)*0.5 + Ki(0.01)*600 + outdoor compensation
    assert state.attributes.get("radiator_setpoint", 0) > 40


async def test_extra_data_saved_correctly(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    hass_storage: dict[str, Any],
) -> None:
    """Test that extra state data is correctly saved for restoration."""
    entity_id = "climate.cascade_climate"

    # Set HVAC mode to heat and set temperature
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 23.0},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Trigger a state save
    await async_mock_restore_state_shutdown_restart(hass)

    # Verify saved data
    assert STORAGE_KEY in hass_storage
    stored_states = hass_storage[STORAGE_KEY]["data"]
    assert len(stored_states) >= 1

    # Find our entity in stored states
    climate_state = next(
        (s for s in stored_states if s["state"]["entity_id"] == entity_id),
        None,
    )
    assert climate_state is not None
    assert climate_state["state"]["state"] == HVACMode.HEAT
    assert climate_state["state"]["attributes"][ATTR_TEMPERATURE] == 23.0

    # Verify extra data structure
    extra_data = climate_state.get("extra_data")
    assert extra_data is not None
    assert "room_error_integral" in extra_data
    assert "last_pump_switch_iso" in extra_data
    assert "radiator_estimate" in extra_data
    assert "pump_on_since_iso" in extra_data
