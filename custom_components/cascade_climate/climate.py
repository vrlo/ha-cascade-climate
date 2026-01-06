"""Climate entity for the Cascade Climate integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import (
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

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
    CONF_UPDATE_INTERVAL,
    DEFAULT_BASE_RADIATOR_TEMP,
    DEFAULT_COOLING_RATE,
    DEFAULT_HEATING_RATE,
    DEFAULT_HYSTERESIS,
    DEFAULT_KI,
    DEFAULT_KP,
    DEFAULT_MIN_CYCLE_DURATION,
    DEFAULT_MIN_RADIATOR_TEMP,
    DEFAULT_OBSERVER_ALPHA,
    DEFAULT_OBSERVER_MODE,
    DEFAULT_OUTDOOR_BASELINE,
    DEFAULT_OUTDOOR_GAIN,
    DEFAULT_PUMP_DEAD_TIME,
    DEFAULT_TARGET_TEMP,
    DEFAULT_TARGET_TEMP_STEP,
    DEFAULT_UPDATE_INTERVAL,
    MAX_RADIATOR_TEMP,
    ObserverMode,
    SUPPLY_WATER_TEMP,
)

LOGGER = logging.getLogger(__name__)


@dataclass
class CascadeClimateConfig:
    """Configuration for the cascade climate controller."""

    room_sensor: str
    radiator_sensor: str
    pump_switch: str
    outside_sensor: str | None
    forecast_entity: str | None
    base_radiator_temp: float
    proportional_gain: float
    integral_gain: float
    min_radiator_temp: float
    hysteresis: float
    min_cycle_duration: timedelta
    update_interval: timedelta
    outdoor_gain: float
    outdoor_baseline: float
    observer_mode: ObserverMode
    heating_rate: float
    cooling_rate: float
    observer_alpha: float
    pump_dead_time: float


class CascadeClimateController:
    """Implements the cascade control logic."""

    def __init__(self, config: CascadeClimateConfig) -> None:
        """Initialize the controller."""
        self._config = config
        self._last_pump_switch: datetime | None = None
        self._pump_state: bool = False
        self._radiator_setpoint: float = config.base_radiator_temp
        self._room_error_integral: float = 0.0
        self._last_integral_update: datetime | None = None

    def compute_radiator_setpoint(
        self,
        *,
        room_target: float,
        room_temp: float | None,
        outside_temp: float | None,
        forecast_temp: float | None,
        now: datetime,
    ) -> float:
        """Compute desired radiator temperature setpoint from room error and feedforward."""
        base = self._config.base_radiator_temp
        kp = self._config.proportional_gain
        ki = self._config.integral_gain
        min_temp = self._config.min_radiator_temp

        radiator_target = base
        proportional_term = 0.0
        integral_term = 0.0
        outdoor_term = 0.0
        forecast_term = 0.0
        error = None
        if room_temp is not None:
            error = room_target - room_temp
            proportional_term = kp * error
            radiator_target += proportional_term

        if error is not None and ki > 0:
            integral_term = self._update_room_integral(error, now)
            radiator_target += ki * integral_term
        else:
            self._last_integral_update = now

        if outside_temp is not None:
            delta = max(0.0, self._config.outdoor_baseline - outside_temp)
            outdoor_term = self._config.outdoor_gain * delta
            radiator_target += outdoor_term

        if forecast_temp is not None:
            delta = max(0.0, self._config.outdoor_baseline - forecast_temp)
            forecast_term = (self._config.outdoor_gain / 2) * delta
            radiator_target += forecast_term

        radiator_target = max(min_temp, min(MAX_RADIATOR_TEMP, radiator_target))
        if LOGGER.isEnabledFor(logging.DEBUG):
            LOGGER.debug(
                "Cascade Climate PI: target %.1f room=%s base=%.1f P=%.3f I=%.3f out=%.3f forecast=%.3f -> %.1f",
                room_target,
                room_temp,
                base,
                proportional_term,
                ki * integral_term if error is not None and ki > 0 else 0.0,
                outdoor_term,
                forecast_term,
                radiator_target,
            )
        self._radiator_setpoint = radiator_target
        return radiator_target

    def _update_room_integral(self, error: float, now: datetime) -> float:
        """Integrate room error with anti-windup."""
        if self._last_integral_update is None:
            self._last_integral_update = now
            return self._room_error_integral

        dt = (now - self._last_integral_update).total_seconds()
        self._last_integral_update = now
        if dt <= 0:
            return self._room_error_integral

        before = self._room_error_integral
        self._room_error_integral += error * dt
        limit = self._integral_limit()
        if limit is not None:
            self._room_error_integral = max(
                -limit, min(limit, self._room_error_integral)
            )
            if (
                LOGGER.isEnabledFor(logging.DEBUG)
                and (
                    self._room_error_integral == -limit
                    or self._room_error_integral == limit
                )
                and before != self._room_error_integral
            ):
                LOGGER.debug(
                    "Cascade Climate PI: integral clamped to %.3f (limit %.3f)",
                    self._room_error_integral,
                    limit,
                )
        return self._room_error_integral

    def _integral_limit(self) -> float | None:
        """Return max absolute integral contribution in error*seconds units."""
        ki = self._config.integral_gain
        if ki <= 0:
            return None
        temp_window = MAX_RADIATOR_TEMP - self._config.min_radiator_temp
        # Limit integral contribution so Ki * integral <= temp_window
        return temp_window / max(ki, 1e-6)

    def reset_integral(self) -> None:
        """Reset integral state."""
        self._room_error_integral = 0.0
        self._last_integral_update = None

    def should_turn_pump_on(
        self,
        *,
        radiator_temp: float | None,
        radiator_target: float,
        now: datetime,
    ) -> bool | None:
        """Determine whether the pump should be on, applying hysteresis and limits."""
        if radiator_temp is None:
            # Insufficient data: keep current state.
            return None

        hysteresis = self._config.hysteresis
        upper_bound = radiator_target + hysteresis / 2
        lower_bound = radiator_target - hysteresis / 2

        if radiator_temp >= MAX_RADIATOR_TEMP:
            return False

        desired_state = self._pump_state
        if self._pump_state:
            if radiator_temp >= upper_bound:
                desired_state = False
        elif radiator_temp <= lower_bound:
            desired_state = True

        if desired_state != self._pump_state:
            if not self._respect_min_cycle(now):
                return None
            return desired_state

        return None

    def _respect_min_cycle(self, now: datetime) -> bool:
        """Check if enough time has passed to allow another pump transition."""
        if self._last_pump_switch is None:
            return True
        return (now - self._last_pump_switch) >= self._config.min_cycle_duration

    def apply_pump_state(self, new_state: bool, *, now: datetime) -> None:
        """Persist the pump state after a successful change."""
        if new_state != self._pump_state:
            self._pump_state = new_state
            self._last_pump_switch = now

    @property
    def radiator_setpoint(self) -> float:
        """Return last radiator setpoint."""
        return self._radiator_setpoint

    @property
    def pump_state(self) -> bool:
        """Return current pump state."""
        return self._pump_state

    @property
    def last_pump_switch(self) -> datetime | None:
        """Return last pump state change timestamp."""
        return self._last_pump_switch


class RadiatorEnergyObserver:
    """Estimate radiator energy/temperature using pump runtime and sensor data."""

    def __init__(self, config: CascadeClimateConfig) -> None:
        """Initialize the observer."""
        self._mode = config.observer_mode
        self._heating_rate = max(0.0, config.heating_rate)
        self._cooling_rate = max(0.0, config.cooling_rate)
        self._alpha = min(1.0, max(0.0, config.observer_alpha))
        self._dead_time = max(0.0, config.pump_dead_time)
        self._min_temp = config.min_radiator_temp
        self._max_temp = MAX_RADIATOR_TEMP
        self._estimate: float | None = config.base_radiator_temp
        self._last_timestamp: datetime | None = None
        self._pump_state: bool = False
        self._pump_on_since: datetime | None = None

    def reset(self, value: float | None = None) -> None:
        """Reset observer state."""
        self._estimate = value
        self._last_timestamp = None
        self._pump_on_since = None
        self._pump_state = False

    def update(
        self,
        *,
        now: datetime,
        pump_on: bool,
        measured_temp: float | None,
    ) -> float | None:
        """Update observer with latest conditions."""
        if self._estimate is None and measured_temp is not None:
            self._estimate = measured_temp

        if self._last_timestamp is None:
            self._last_timestamp = now
            self._pump_state = pump_on
            if pump_on:
                self._pump_on_since = now
            return self._estimate

        dt = (now - self._last_timestamp).total_seconds()
        if dt < 0:
            dt = 0
        self._last_timestamp = now

        if pump_on and not self._pump_state:
            self._pump_on_since = now
        elif not pump_on:
            self._pump_on_since = None

        predicted = self._estimate if self._estimate is not None else measured_temp
        if predicted is None:
            predicted = self._min_temp

        rate = 0.0
        if pump_on:
            if self._pump_on_since is not None:
                elapsed = (now - self._pump_on_since).total_seconds()
                if elapsed >= self._dead_time:
                    rate = self._heating_rate
            else:
                rate = self._heating_rate
        else:
            rate = -self._cooling_rate

        predicted = self._clamp(predicted + rate * dt)
        blended = self._blend(predicted, measured_temp)
        if LOGGER.isEnabledFor(logging.DEBUG):
            LOGGER.debug(
                "Cascade Climate observer (%s): pump=%s meas=%s pred=%.2f rate=%.3f -> %.2f",
                self._mode.value,
                pump_on,
                measured_temp,
                predicted,
                rate,
                blended,
            )
        self._estimate = blended
        self._pump_state = pump_on
        return self._estimate

    def _blend(self, predicted: float, measured: float | None) -> float:
        """Blend predicted and measured temperatures based on observer mode."""
        if self._mode == ObserverMode.RUNTIME:
            return predicted
        if measured is None:
            return predicted
        if self._mode == ObserverMode.SENSOR:
            return measured
        # Fusion
        return (self._alpha * measured) + ((1 - self._alpha) * predicted)

    def _clamp(self, value: float) -> float:
        """Clamp value to valid radiator temperature range."""
        return max(self._min_temp, min(self._max_temp, value))

    @property
    def estimate(self) -> float | None:
        """Return current estimated radiator temperature."""
        return self._estimate


@dataclass
class CascadeClimateExtraStoredData(ExtraStoredData):
    """Extra stored data for cascade climate state restoration."""

    room_error_integral: float
    last_pump_switch_iso: str | None
    radiator_estimate: float | None
    pump_on_since_iso: str | None

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict."""
        return {
            "room_error_integral": self.room_error_integral,
            "last_pump_switch_iso": self.last_pump_switch_iso,
            "radiator_estimate": self.radiator_estimate,
            "pump_on_since_iso": self.pump_on_since_iso,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CascadeClimateExtraStoredData | None:
        """Restore from dict."""
        if not isinstance(data, dict):
            return None
        try:
            return cls(
                room_error_integral=float(data.get("room_error_integral", 0.0)),
                last_pump_switch_iso=data.get("last_pump_switch_iso"),
                radiator_estimate=data.get("radiator_estimate"),
                pump_on_since_iso=data.get("pump_on_since_iso"),
            )
        except (TypeError, ValueError):
            return None


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: Callable[[list[ClimateEntity]], None],
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up from YAML (not supported)."""
    return


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the climate platform."""
    # Prefer runtime_data prepared in __init__
    config = (
        entry.runtime_data
        if getattr(entry, "runtime_data", None)
        else _entry_to_config(entry)
    )

    entity = CascadeClimateEntity(
        hass, entry.entry_id, entry.title or "Cascade Climate", config
    )
    async_add_entities([entity])


def _entry_to_config(entry) -> CascadeClimateConfig:
    """Translate a config entry into CascadeClimateConfig."""
    data = entry.data
    options = entry.options

    def _get_float(key: str, default: float) -> float:
        value = options.get(key, data.get(key, default))
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _get_timedelta(key: str, default: timedelta) -> timedelta:
        value = options.get(key, data.get(key))
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return timedelta(seconds=float(value))
        if isinstance(value, dict):
            seconds = value.get("seconds")
            if seconds is not None:
                return timedelta(seconds=float(seconds))
        return default

    def _get_observer_mode(primary: str | None, override: str | None) -> ObserverMode:
        raw = override or primary or DEFAULT_OBSERVER_MODE
        try:
            return ObserverMode(raw)
        except ValueError:
            return ObserverMode(DEFAULT_OBSERVER_MODE)

    return CascadeClimateConfig(
        room_sensor=data[ATTR_ROOM_SENSOR],
        radiator_sensor=data[ATTR_RADIATOR_SENSOR],
        pump_switch=data[ATTR_PUMP_SWITCH],
        outside_sensor=data.get(ATTR_OUTSIDE_SENSOR)
        or options.get(ATTR_OUTSIDE_SENSOR),
        forecast_entity=data.get(ATTR_FORECAST_ENTITY)
        or options.get(ATTR_FORECAST_ENTITY),
        base_radiator_temp=_get_float(
            CONF_BASE_RADIATOR_TEMP, DEFAULT_BASE_RADIATOR_TEMP
        ),
        proportional_gain=_get_float(CONF_KP, DEFAULT_KP),
        integral_gain=_get_float(CONF_KI, DEFAULT_KI),
        min_radiator_temp=_get_float(CONF_MIN_RADIATOR_TEMP, DEFAULT_MIN_RADIATOR_TEMP),
        hysteresis=_get_float(CONF_HYSTERESIS, DEFAULT_HYSTERESIS),
        min_cycle_duration=_get_timedelta(
            CONF_MIN_CYCLE_DURATION, DEFAULT_MIN_CYCLE_DURATION
        ),
        update_interval=_get_timedelta(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
        outdoor_gain=_get_float(CONF_OUTDOOR_GAIN, DEFAULT_OUTDOOR_GAIN),
        outdoor_baseline=_get_float(CONF_OUTDOOR_BASELINE, DEFAULT_OUTDOOR_BASELINE),
        observer_mode=_get_observer_mode(
            data.get(CONF_OBSERVER_MODE),
            options.get(CONF_OBSERVER_MODE),
        ),
        heating_rate=_get_float(CONF_HEATING_RATE, DEFAULT_HEATING_RATE),
        cooling_rate=_get_float(CONF_COOLING_RATE, DEFAULT_COOLING_RATE),
        observer_alpha=_get_float(CONF_OBSERVER_ALPHA, DEFAULT_OBSERVER_ALPHA),
        pump_dead_time=_get_float(CONF_PUMP_DEAD_TIME, DEFAULT_PUMP_DEAD_TIME),
    )


class CascadeClimateEntity(ClimateEntity, RestoreEntity):
    """Representation of the cascade-controlled climate entity."""

    _attr_should_poll = False
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_max_temp = 30.0
    _attr_min_temp = 10.0
    _attr_target_temperature_step = DEFAULT_TARGET_TEMP_STEP
    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        name: str,
        config: CascadeClimateConfig,
    ) -> None:
        """Initialize the entity."""
        self.hass = hass
        self._config = config
        self._controller = CascadeClimateController(config)
        self._attr_name = name
        self._attr_unique_id = f"{entry_id}-climate"
        self._attr_hvac_mode = HVACMode.OFF  # Safe default for new installations
        self._target_temperature = DEFAULT_TARGET_TEMP
        self._energy_observer = RadiatorEnergyObserver(config)

        self._room_temp: float | None = None
        self._radiator_temp: float | None = None
        self._outside_temp: float | None = None
        self._forecast_temp: float | None = None
        self._estimated_radiator_temp: float | None = None

        self._unsub_listeners: list[Callable[[], None]] = []

    async def async_added_to_hass(self) -> None:
        """Register callbacks when entity added to hass."""
        await super().async_added_to_hass()

        # Restore previous state before setting up listeners
        await self._async_restore_state()

        @callback
        def _handle_room(event: Event[EventStateChangedData]) -> None:
            self._room_temp = _coerce_temp(event.data.get("new_state"))
            self._schedule_control("room-update")

        @callback
        def _handle_radiator(event: Event[EventStateChangedData]) -> None:
            self._radiator_temp = _coerce_temp(event.data.get("new_state"))
            self._schedule_control("radiator-update")

        @callback
        def _handle_outside(event: Event[EventStateChangedData]) -> None:
            self._outside_temp = _coerce_temp(event.data.get("new_state"))
            self._schedule_control("outside-update")

        self._unsub_listeners.append(
            async_track_state_change_event(
                self.hass, [self._config.room_sensor], _handle_room
            )
        )
        self._unsub_listeners.append(
            async_track_state_change_event(
                self.hass, [self._config.radiator_sensor], _handle_radiator
            )
        )

        @callback
        def _handle_pump(event: Event[EventStateChangedData]) -> None:
            if self._sync_pump_state(event.data.get("new_state")):
                self.async_write_ha_state()

        self._unsub_listeners.append(
            async_track_state_change_event(
                self.hass, [self._config.pump_switch], _handle_pump
            )
        )

        if self._config.outside_sensor:
            self._unsub_listeners.append(
                async_track_state_change_event(
                    self.hass, [self._config.outside_sensor], _handle_outside
                )
            )

        async def _interval(now) -> None:
            await self._refresh_sensor_cache()
            await self._evaluate_control("interval")

        self._unsub_listeners.append(
            async_track_time_interval(
                self.hass, _interval, self._config.update_interval
            )
        )

        await self._refresh_sensor_cache()
        await self._evaluate_control("initial")

    async def _async_restore_state(self) -> None:
        """Restore previous entity state and internal controller state."""
        old_state = await self.async_get_last_state()
        extra_data = await self.async_get_last_extra_data()

        if old_state is not None:
            # Restore HVAC mode from state value
            if old_state.state and old_state.state in [m.value for m in HVACMode]:
                self._attr_hvac_mode = HVACMode(old_state.state)
                LOGGER.debug("Restored HVAC mode: %s", self._attr_hvac_mode)

            # Restore target temperature from attributes
            if (temp := old_state.attributes.get(ATTR_TEMPERATURE)) is not None:
                try:
                    self._target_temperature = float(temp)
                    LOGGER.debug(
                        "Restored target temperature: %s", self._target_temperature
                    )
                except (TypeError, ValueError):
                    pass

        if extra_data is not None:
            restored = CascadeClimateExtraStoredData.from_dict(extra_data.as_dict())
            if restored is not None:
                self._restore_controller_state(restored)

    def _restore_controller_state(self, data: CascadeClimateExtraStoredData) -> None:
        """Restore internal controller and observer state."""
        # Restore PI integral
        self._controller._room_error_integral = data.room_error_integral
        LOGGER.debug("Restored PI integral: %s", data.room_error_integral)

        # Restore last pump switch timestamp
        if data.last_pump_switch_iso:
            try:
                self._controller._last_pump_switch = dt_util.parse_datetime(
                    data.last_pump_switch_iso
                )
            except (TypeError, ValueError):
                pass

        # Restore observer estimate
        if data.radiator_estimate is not None:
            self._energy_observer._estimate = data.radiator_estimate
            self._estimated_radiator_temp = data.radiator_estimate
            LOGGER.debug("Restored radiator estimate: %s", data.radiator_estimate)

        # Restore pump_on_since for observer dead time tracking
        if data.pump_on_since_iso:
            try:
                self._energy_observer._pump_on_since = dt_util.parse_datetime(
                    data.pump_on_since_iso
                )
            except (TypeError, ValueError):
                pass

    async def async_will_remove_from_hass(self) -> None:
        """Clean up listeners when entity removed."""
        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners.clear()

    @property
    def current_temperature(self) -> float | None:
        """Return the current room temperature."""
        return self._room_temp

    @property
    def target_temperature(self) -> float | None:
        """Return target room temperature."""
        return self._target_temperature

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current heating/cooling action."""
        if self._attr_hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        if self._controller.pump_state:
            return HVACAction.HEATING
        return HVACAction.IDLE

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose additional attributes."""
        return {
            "radiator_temperature": self._radiator_temp,
            "radiator_setpoint": self._controller.radiator_setpoint,
            "estimated_radiator_temperature": self._estimated_radiator_temp,
            "outside_temperature": self._outside_temp,
            "forecast_temperature": self._forecast_temp,
            "pump_state": self._controller.pump_state,
            "observer_mode": self._config.observer_mode.value,
            "supply_water_temperature": SUPPLY_WATER_TEMP,
            "max_radiator_temperature": MAX_RADIATOR_TEMP,
        }

    @property
    def extra_restore_state_data(self) -> CascadeClimateExtraStoredData:
        """Return extra state data to be saved for restoration."""
        return CascadeClimateExtraStoredData(
            room_error_integral=self._controller._room_error_integral,
            last_pump_switch_iso=(
                self._controller._last_pump_switch.isoformat()
                if self._controller._last_pump_switch
                else None
            ),
            radiator_estimate=self._energy_observer._estimate,
            pump_on_since_iso=(
                self._energy_observer._pump_on_since.isoformat()
                if self._energy_observer._pump_on_since
                else None
            ),
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        self._target_temperature = float(temperature)
        self._controller.reset_integral()
        self._energy_observer.reset(self._radiator_temp)
        self._estimated_radiator_temp = self._radiator_temp
        await self._evaluate_control("set-temperature")

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        if hvac_mode not in self.hvac_modes:
            raise ValueError(f"Unsupported hvac mode {hvac_mode}")
        self._attr_hvac_mode = hvac_mode
        if hvac_mode == HVACMode.OFF:
            await self._set_pump(False, reason="hvac-off")
            self._controller.reset_integral()
            self._energy_observer.reset(self._radiator_temp)
            self._estimated_radiator_temp = self._radiator_temp
            self.async_write_ha_state()
            return

        await self._evaluate_control("hvac-on")

    async def _refresh_sensor_cache(self) -> None:
        """Fetch latest sensor states."""
        self._room_temp = _coerce_temp(self.hass.states.get(self._config.room_sensor))
        self._radiator_temp = _coerce_temp(
            self.hass.states.get(self._config.radiator_sensor)
        )

        if self._config.outside_sensor:
            self._outside_temp = _coerce_temp(
                self.hass.states.get(self._config.outside_sensor)
            )

        if self._config.forecast_entity:
            self._forecast_temp = _extract_forecast_temp(
                self.hass.states.get(self._config.forecast_entity)
            )

        self._sync_pump_state(self.hass.states.get(self._config.pump_switch))

    async def _evaluate_control(self, reason: str) -> None:
        """Run cascade control using the latest sensor values."""
        if self._attr_hvac_mode == HVACMode.OFF:
            await self._set_pump(False, reason=f"{reason}-hvac-off")
            self._controller.reset_integral()
            self._energy_observer.reset(self._radiator_temp)
            self._estimated_radiator_temp = self._radiator_temp
            self.async_write_ha_state()
            return

        await self._refresh_forecast_if_needed()
        now = dt_util.utcnow()
        radiator_setpoint = self._controller.compute_radiator_setpoint(
            room_target=self._target_temperature,
            room_temp=self._room_temp,
            outside_temp=self._outside_temp,
            forecast_temp=self._forecast_temp,
            now=now,
        )

        self._estimated_radiator_temp = self._energy_observer.update(
            now=now,
            pump_on=self._controller.pump_state,
            measured_temp=self._radiator_temp,
        )
        if (
            LOGGER.isEnabledFor(logging.DEBUG)
            and self._estimated_radiator_temp is not None
        ):
            LOGGER.debug(
                "Cascade Climate observer estimate: %.2f°C (sensor=%s, mode=%s)",
                self._estimated_radiator_temp,
                self._radiator_temp,
                self._config.observer_mode.value,
            )

        desired_state = self._controller.should_turn_pump_on(
            radiator_temp=self._estimated_radiator_temp
            if self._estimated_radiator_temp is not None
            else self._radiator_temp,
            radiator_target=radiator_setpoint,
            now=now,
        )

        if desired_state is None:
            LOGGER.debug("Cascade Climate: no pump change (%s)", reason)
        else:
            await self._set_pump(desired_state, reason=reason, timestamp=now)

        self.async_write_ha_state()

    async def _refresh_forecast_if_needed(self) -> None:
        """Refresh forecast data when available."""
        if not self._config.forecast_entity:
            return
        state = self.hass.states.get(self._config.forecast_entity)
        self._forecast_temp = _extract_forecast_temp(state)

    async def _set_pump(
        self, turn_on: bool, *, reason: str, timestamp: datetime | None = None
    ) -> None:
        """Call HA service to adjust pump switch."""
        if timestamp is None:
            timestamp = dt_util.utcnow()

        if self._controller.pump_state == turn_on:
            return

        service = "turn_on" if turn_on else "turn_off"
        LOGGER.debug("Cascade Climate: %s pump because %s", service, reason)
        await self.hass.services.async_call(
            "switch",
            service,
            {ATTR_ENTITY_ID: self._config.pump_switch},
            blocking=False,
        )
        self._controller.apply_pump_state(turn_on, now=timestamp)

    async def async_update(self) -> None:
        """Update entity state (not used but kept for completeness)."""
        await self._refresh_sensor_cache()

    def _schedule_control(self, reason: str) -> None:
        """Schedule control evaluation from a sync context."""
        self.hass.async_create_task(self._evaluate_control(reason))

    def _sync_pump_state(self, state: State | None) -> bool:
        """Sync controller pump state with actual switch state."""
        actual = _coerce_switch_state(state)
        if actual is None:
            return False

        if actual == self._controller.pump_state:
            return False

        self._controller.apply_pump_state(actual, now=dt_util.utcnow())
        return True


def _coerce_temp(state: State | None) -> float | None:
    """Convert a Home Assistant state to a temperature float."""
    if state is None or state.state in ("unknown", "unavailable"):
        return None
    try:
        return float(state.state)
    except (TypeError, ValueError):
        return None


def _extract_forecast_temp(state: State | None) -> float | None:
    """Extract forecast temperature from a weather entity."""
    if state is None:
        return None

    temperature = state.attributes.get("temperature")
    if isinstance(temperature, (int, float)):
        return float(temperature)

    forecast = state.attributes.get("forecast")
    if isinstance(forecast, list) and forecast:
        first = forecast[0]
        temp = first.get("temperature")
        if isinstance(temp, (int, float)):
            return float(temp)

    return None


def _coerce_switch_state(state: State | None) -> bool | None:
    """Convert a Home Assistant switch state to bool."""
    if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
        return None
    return state.state == STATE_ON
