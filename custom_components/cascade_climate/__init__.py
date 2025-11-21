"""Init file for the Cascade Climate integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .climate import _entry_to_config
from .const import DOMAIN

LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration via YAML.

    This integration is configured via the UI and does not support YAML options.
    Define an empty config schema to satisfy hassfest.
    """
    hass.data.setdefault(DOMAIN, {})
    return True


# Config entries only, no YAML configuration supported
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Cascade Climate from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    data = entry.data
    missing = [
        key
        for key in ("room_sensor", "radiator_sensor", "pump_switch")
        if not hass.states.get(data.get(key, ""))
    ]
    if missing:
        raise ConfigEntryNotReady(f"Missing required entities: {', '.join(missing)}")

    # Store computed runtime configuration
    entry.runtime_data = _entry_to_config(entry)
    hass.data[DOMAIN][entry.entry_id] = {}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    LOGGER.debug("Cascade Climate entry %s set up", entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        LOGGER.debug("Cascade Climate entry %s unloaded", entry.entry_id)
    return unload_ok
