"""Config flow for the Cascade Climate integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
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
    MAX_RADIATOR_TEMP,
    ObserverMode,
)


class CascadeClimateConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Cascade Climate."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            data = dict(user_input)
            title = data.pop("name")

            # Prevent duplicates: use a stable unique id derived from key entities
            # Use pump switch as the unique identifier; multiple entries
            # controlling the same pump do not make sense
            unique_id = str(data.get(ATTR_PUMP_SWITCH, ""))
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            data.setdefault(CONF_BASE_RADIATOR_TEMP, DEFAULT_BASE_RADIATOR_TEMP)
            data.setdefault(CONF_KP, DEFAULT_KP)
            data.setdefault(CONF_KI, DEFAULT_KI)
            data.setdefault(CONF_MIN_RADIATOR_TEMP, DEFAULT_MIN_RADIATOR_TEMP)
            data.setdefault(CONF_HYSTERESIS, DEFAULT_HYSTERESIS)
            # Programmatic polling intervals (not user-configurable for Bronze)
            data.setdefault(
                CONF_MIN_CYCLE_DURATION, DEFAULT_MIN_CYCLE_DURATION.total_seconds()
            )
            data.setdefault(CONF_OUTDOOR_GAIN, DEFAULT_OUTDOOR_GAIN)
            data.setdefault(CONF_OUTDOOR_BASELINE, DEFAULT_OUTDOOR_BASELINE)
            data.setdefault(CONF_OBSERVER_MODE, ObserverMode.SENSOR.value)
            data.setdefault(CONF_HEATING_RATE, DEFAULT_HEATING_RATE)
            data.setdefault(CONF_COOLING_RATE, DEFAULT_COOLING_RATE)
            data.setdefault(CONF_OBSERVER_ALPHA, DEFAULT_OBSERVER_ALPHA)
            data.setdefault(CONF_PUMP_DEAD_TIME, DEFAULT_PUMP_DEAD_TIME)

            return self.async_create_entry(title=title, data=data)

        schema = vol.Schema(
            {
                vol.Required(
                    "name", default="Cascade Climate"
                ): selector.TextSelector(),
                vol.Required(ATTR_ROOM_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor", device_class="temperature"
                    )
                ),
                vol.Required(ATTR_RADIATOR_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor", device_class="temperature"
                    )
                ),
                vol.Required(ATTR_PUMP_SWITCH): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="switch")
                ),
                vol.Optional(ATTR_OUTSIDE_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor", device_class="temperature"
                    )
                ),
                vol.Optional(ATTR_FORECAST_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="weather")
                ),
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Return the options flow handler."""
        return CascadeClimateOptionsFlow(config_entry)


class CascadeClimateOptionsFlow(OptionsFlow):
    """Handle options for Cascade Climate."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=dict(user_input))

        data = {**self._entry.data, **self._entry.options}

        schema = vol.Schema(
            {
                vol.Optional(
                    ATTR_OUTSIDE_SENSOR,
                    default=data.get(ATTR_OUTSIDE_SENSOR),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor", device_class="temperature"
                    )
                ),
                vol.Optional(
                    ATTR_FORECAST_ENTITY,
                    default=data.get(ATTR_FORECAST_ENTITY),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="weather")
                ),
                vol.Required(
                    CONF_BASE_RADIATOR_TEMP,
                    default=data.get(
                        CONF_BASE_RADIATOR_TEMP, DEFAULT_BASE_RADIATOR_TEMP
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=10,
                        max=60,
                        step=0.5,
                        unit_of_measurement="°C",
                    )
                ),
                vol.Required(
                    CONF_KP,
                    default=data.get(CONF_KP, DEFAULT_KP),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=20,
                        step=0.5,
                    )
                ),
                vol.Required(
                    CONF_KI,
                    default=data.get(CONF_KI, DEFAULT_KI),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=5,
                        step=0.05,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_MIN_RADIATOR_TEMP,
                    default=data.get(CONF_MIN_RADIATOR_TEMP, DEFAULT_MIN_RADIATOR_TEMP),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=10,
                        max=MAX_RADIATOR_TEMP,
                        step=0.5,
                        unit_of_measurement="°C",
                    )
                ),
                vol.Required(
                    CONF_HYSTERESIS,
                    default=data.get(CONF_HYSTERESIS, DEFAULT_HYSTERESIS),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.1,
                        max=5,
                        step=0.1,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                # update interval is set by integration logic; not user-configurable
                vol.Required(
                    CONF_MIN_CYCLE_DURATION,
                    default=data.get(
                        CONF_MIN_CYCLE_DURATION,
                        DEFAULT_MIN_CYCLE_DURATION.total_seconds(),
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=30,
                        max=900,
                        step=15,
                        unit_of_measurement="s",
                    )
                ),
                vol.Required(
                    CONF_OUTDOOR_GAIN,
                    default=data.get(CONF_OUTDOOR_GAIN, DEFAULT_OUTDOOR_GAIN),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=5,
                        step=0.1,
                    )
                ),
                vol.Required(
                    CONF_OUTDOOR_BASELINE,
                    default=data.get(CONF_OUTDOOR_BASELINE, DEFAULT_OUTDOOR_BASELINE),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=-20,
                        max=30,
                        step=0.5,
                        unit_of_measurement="°C",
                    )
                ),
                vol.Required(
                    CONF_OBSERVER_MODE,
                    default=data.get(CONF_OBSERVER_MODE, ObserverMode.SENSOR.value),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[mode.value for mode in ObserverMode],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        translation_key="observer_mode",
                    )
                ),
                vol.Required(
                    CONF_HEATING_RATE,
                    default=data.get(CONF_HEATING_RATE, DEFAULT_HEATING_RATE),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=1,
                        step=0.01,
                        unit_of_measurement="°C/s",
                    )
                ),
                vol.Required(
                    CONF_COOLING_RATE,
                    default=data.get(CONF_COOLING_RATE, DEFAULT_COOLING_RATE),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=1,
                        step=0.01,
                        unit_of_measurement="°C/s",
                    )
                ),
                vol.Required(
                    CONF_OBSERVER_ALPHA,
                    default=data.get(CONF_OBSERVER_ALPHA, DEFAULT_OBSERVER_ALPHA),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=1,
                        step=0.05,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_PUMP_DEAD_TIME,
                    default=data.get(CONF_PUMP_DEAD_TIME, DEFAULT_PUMP_DEAD_TIME),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=60,
                        step=1,
                        unit_of_measurement="s",
                    )
                ),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
