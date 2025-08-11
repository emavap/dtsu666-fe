"""The DTSU666 Emulator integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .modbus_server import DTSU666ModbusServer

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up DTSU666 Emulator from a config entry."""
    try:
        # Validate configuration data
        if not _validate_entry_data(entry):
            return False
            
        # Create and start the Modbus server
        server = DTSU666ModbusServer(
            hass=hass,
            host=entry.data["host"],
            port=entry.data["port"],
            slave_id=entry.data["slave_id"],
            entity_mappings=entry.data.get("entity_mappings", {}),
            update_interval=entry.options.get("update_interval", entry.data.get("update_interval", 5)),
        )

        if not await server.start():
            _LOGGER.error("Failed to start DTSU666 Modbus server on %s:%d", 
                         entry.data["host"], entry.data["port"])
            raise ConfigEntryNotReady("Failed to start Modbus server")

        # Store server instance
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][entry.entry_id] = server

        # Setup platforms with error handling
        try:
            await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        except Exception as ex:
            _LOGGER.error("Failed to set up platforms: %s", ex)
            await server.stop()
            hass.data[DOMAIN].pop(entry.entry_id, None)
            return False

        # Add update listener for configuration changes
        entry.async_on_unload(entry.add_update_listener(async_update_options))

        _LOGGER.info("DTSU666 Emulator integration setup completed successfully")
        return True

    except ConfigEntryNotReady:
        raise  # Re-raise ConfigEntryNotReady without wrapping
    except Exception as ex:
        _LOGGER.error("Failed to setup DTSU666 Emulator: %s", ex, exc_info=True)
        return False


def _validate_entry_data(entry: ConfigEntry) -> bool:
    """Validate configuration entry data."""
    try:
        required_fields = ["host", "port", "slave_id"]
        for field in required_fields:
            if field not in entry.data:
                _LOGGER.error("Missing required configuration field: %s", field)
                return False
                
        # Validate data types and ranges
        if not isinstance(entry.data["host"], str) or not entry.data["host"]:
            _LOGGER.error("Invalid host configuration")
            return False
            
        port = entry.data["port"]
        if not isinstance(port, int) or not (1 <= port <= 65535):
            _LOGGER.error("Invalid port configuration: %s", port)
            return False
            
        slave_id = entry.data["slave_id"]
        if not isinstance(slave_id, int) or not (1 <= slave_id <= 247):
            _LOGGER.error("Invalid slave_id configuration: %s", slave_id)
            return False
            
        return True
        
    except Exception as ex:
        _LOGGER.error("Error validating entry data: %s", ex)
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


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)