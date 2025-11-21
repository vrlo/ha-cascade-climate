"""Test the Cascade Climate integration setup."""

import pytest

from custom_components.cascade_climate.const import DOMAIN

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from pytest_homeassistant_custom_component.common import MockConfigEntry


async def test_setup_and_unload(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test setup and unload."""
    entry = init_integration

    assert entry.state is ConfigEntryState.LOADED
    assert DOMAIN in hass.data

    # Test unload
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert entry.entry_id not in hass.data.get(DOMAIN, {})


async def test_setup_missing_entities(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup with missing required entities raises ConfigEntryNotReady."""
    # Don't create mock entities
    mock_config_entry.add_to_hass(hass)

    # Setup should fail with ConfigEntryNotReady
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_partial_missing_entities(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup with some missing required entities."""
    # Create only some entities
    hass.states.async_set("sensor.room_temperature", "20.0")
    hass.states.async_set("sensor.radiator_temperature", "30.0")
    # Missing pump switch

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_yaml_config_disabled(hass: HomeAssistant) -> None:
    """Test that YAML configuration is properly disabled."""
    from custom_components.cascade_climate import async_setup

    # YAML config should succeed but not do anything
    result = await async_setup(hass, {DOMAIN: {}})
    assert result is True
    assert DOMAIN in hass.data
    assert hass.data[DOMAIN] == {}
