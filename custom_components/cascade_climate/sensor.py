"""Sensor platform for the Cascade Climate integration."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .climate import CascadeClimateConfig


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    config: CascadeClimateConfig = entry.runtime_data
    climate_entity_id = f"climate.{entry.title.lower().replace(' ', '_')}"

    entities = [
        CascadeRadiatorSetpointSensor(
            hass, entry.entry_id, entry.title, config, climate_entity_id
        ),
        CascadeRadiatorTemperatureSensor(
            hass, entry.entry_id, entry.title, config, climate_entity_id
        ),
    ]

    async_add_entities(entities)


class CascadeRadiatorSetpointSensor(SensorEntity):
    """Sensor for the radiator temperature setpoint."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        name: str,
        config: CascadeClimateConfig,
        climate_entity_id: str,
    ) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._config = config
        self._climate_entity_id = climate_entity_id
        self._attr_name = "Radiator setpoint"
        self._attr_unique_id = f"{entry_id}-radiator-setpoint"
        self._attr_native_value = None

    async def async_added_to_hass(self) -> None:
        """Register callbacks when entity added to hass."""
        await super().async_added_to_hass()

        @callback
        def _handle_climate_update(event) -> None:
            """Update sensor when climate entity changes."""
            state = event.data.get("new_state")
            if state is None:
                return

            # Get radiator_setpoint from climate entity attributes
            radiator_setpoint = state.attributes.get("radiator_setpoint")
            if radiator_setpoint is not None:
                self._attr_native_value = float(radiator_setpoint)
                self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._climate_entity_id], _handle_climate_update
            )
        )

        # Initialize with current state
        climate_state = self.hass.states.get(self._climate_entity_id)
        if climate_state:
            radiator_setpoint = climate_state.attributes.get("radiator_setpoint")
            if radiator_setpoint is not None:
                self._attr_native_value = float(radiator_setpoint)


class CascadeRadiatorTemperatureSensor(SensorEntity):
    """Sensor for the current radiator temperature."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        name: str,
        config: CascadeClimateConfig,
        climate_entity_id: str,
    ) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._config = config
        self._climate_entity_id = climate_entity_id
        self._attr_name = "Radiator temperature"
        self._attr_unique_id = f"{entry_id}-radiator-temperature"
        self._attr_native_value = None

    async def async_added_to_hass(self) -> None:
        """Register callbacks when entity added to hass."""
        await super().async_added_to_hass()

        @callback
        def _handle_climate_update(event) -> None:
            """Update sensor when climate entity changes."""
            state = event.data.get("new_state")
            if state is None:
                return

            # Get radiator_temperature from climate entity attributes
            radiator_temp = state.attributes.get("radiator_temperature")
            if radiator_temp is not None:
                self._attr_native_value = float(radiator_temp)
                self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._climate_entity_id], _handle_climate_update
            )
        )

        # Initialize with current state
        climate_state = self.hass.states.get(self._climate_entity_id)
        if climate_state:
            radiator_temp = climate_state.attributes.get("radiator_temperature")
            if radiator_temp is not None:
                self._attr_native_value = float(radiator_temp)
