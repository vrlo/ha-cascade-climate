"""Constants for the Cascade Climate integration."""

from datetime import timedelta
from enum import StrEnum

DOMAIN = "cascade_climate"

ATTR_ROOM_SENSOR = "room_sensor"
ATTR_RADIATOR_SENSOR = "radiator_sensor"
ATTR_OUTSIDE_SENSOR = "outside_sensor"
ATTR_FORECAST_ENTITY = "forecast_entity"
ATTR_PUMP_SWITCH = "pump_switch"

CONF_BASE_RADIATOR_TEMP = "base_radiator_temp"
CONF_KP = "proportional_gain"
CONF_KI = "integral_gain"
CONF_MIN_RADIATOR_TEMP = "min_radiator_temp"
CONF_HYSTERESIS = "hysteresis"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_MIN_CYCLE_DURATION = "min_cycle_duration"
CONF_OUTDOOR_GAIN = "outdoor_gain"
CONF_OUTDOOR_BASELINE = "outdoor_baseline"
CONF_OBSERVER_MODE = "observer_mode"
CONF_HEATING_RATE = "heating_rate"
CONF_COOLING_RATE = "cooling_rate"
CONF_OBSERVER_ALPHA = "observer_alpha"
CONF_PUMP_DEAD_TIME = "pump_dead_time"

DEFAULT_BASE_RADIATOR_TEMP = 35.0
DEFAULT_KP = 8.0
DEFAULT_KI = 0.0
DEFAULT_MIN_RADIATOR_TEMP = 25.0
DEFAULT_HYSTERESIS = 1.0
DEFAULT_UPDATE_INTERVAL = timedelta(seconds=30)
DEFAULT_MIN_CYCLE_DURATION = timedelta(minutes=2)
DEFAULT_OUTDOOR_GAIN = 0.3
DEFAULT_OUTDOOR_BASELINE = 10.0
DEFAULT_OBSERVER_MODE = "sensor"
DEFAULT_HEATING_RATE = 0.25  # °C per second while pump on after dead time
DEFAULT_COOLING_RATE = 0.05  # °C per second while pump off
DEFAULT_OBSERVER_ALPHA = 0.5
DEFAULT_PUMP_DEAD_TIME = 5.0  # seconds

MAX_RADIATOR_TEMP = 50.0
SUPPLY_WATER_TEMP = 74.0

# Climate entity defaults
DEFAULT_TARGET_TEMP = 21.0
DEFAULT_TARGET_TEMP_STEP = 0.5
DEFAULT_ROOM_TEMP_UNIT = "°C"


class ObserverMode(StrEnum):
    """Available observer modes for radiator energy estimation."""

    SENSOR = "sensor"
    RUNTIME = "runtime"
    FUSION = "fusion"
