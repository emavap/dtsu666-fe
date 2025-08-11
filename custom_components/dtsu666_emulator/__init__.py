"""The DTSU666 Emulator integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .modbus_server import DTSU666ModbusServer

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = []


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up DTSU666 Emulator from a config entry."""
    try:
        # Create and start the Modbus server
        server = DTSU666ModbusServer(
            hass=hass,
            host=entry.data["host"],
            port=entry.data["port"],
            slave_id=entry.data["slave_id"],
            entity_mappings=entry.data["entity_mappings"],
            update_interval=entry.options.get("update_interval", entry.data["update_interval"]),
        )

        if not await server.start():
            raise ConfigEntryNotReady("Failed to start Modbus server")

        # Store server instance
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][entry.entry_id] = server

        # Setup platforms
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

        return True

    except Exception as ex:
        _LOGGER.error("Failed to setup DTSU666 Emulator: %s", ex)
        return False


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Stop the Modbus server
    server: DTSU666ModbusServer = hass.data[DOMAIN][entry.entry_id]
    await server.stop()

    # Unload platforms
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)