"""Utility functions for DTSU666 Emulator integration."""
from __future__ import annotations

import ipaddress
import logging
from typing import Any

from homeassistant.core import HomeAssistant

from .const import REQUIRED_ENTITIES

_LOGGER = logging.getLogger(__name__)


def is_valid_host(host: str) -> bool:
    """Validate host address."""
    if host in ("0.0.0.0", "localhost"):
        return True
    
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def get_device_class_for_entity(entity_type: str) -> str | None:
    """Get device class for entity type."""
    if "voltage" in entity_type:
        return "voltage"
    elif "current" in entity_type:
        return "current"
    elif "power" in entity_type:
        return "power"
    elif "energy" in entity_type:
        return "energy"
    elif "frequency" in entity_type:
        return "frequency"
    return None


def validate_network_settings(user_input: dict[str, Any]) -> dict[str, str]:
    """Validate network settings and return errors."""
    from .const import CONF_HOST, CONF_PORT, CONF_SLAVE_ID
    
    errors: dict[str, str] = {}
    
    if not is_valid_host(user_input[CONF_HOST]):
        errors[CONF_HOST] = "invalid_host"
    elif not (1 <= user_input[CONF_PORT] <= 65535):
        errors[CONF_PORT] = "invalid_port"
    elif not (1 <= user_input[CONF_SLAVE_ID] <= 247):
        errors[CONF_SLAVE_ID] = "invalid_slave_id"
        
    return errors


def validate_entity_mappings(
    hass: HomeAssistant, 
    entity_mappings: dict[str, str]
) -> dict[str, str]:
    """Validate entity mappings and return errors."""
    errors: dict[str, str] = {}
    
    # Validate required entities are mapped
    missing_required = [
        entity_type for entity_type in REQUIRED_ENTITIES
        if not entity_mappings.get(entity_type)
    ]
    
    if missing_required:
        errors["base"] = "missing_required_entities"
        _LOGGER.error("Missing required entities: %s", missing_required)
        return errors
    
    # Validate entity IDs exist
    invalid_entities = []
    for entity_type, entity_id in entity_mappings.items():
        if entity_id and not hass.states.get(entity_id):
            invalid_entities.append(f"{entity_type}: {entity_id}")
    
    if invalid_entities:
        errors["base"] = "invalid_entities"
        _LOGGER.error("Invalid entities: %s", invalid_entities)
    
    return errors


def parse_entity_mappings(user_input: dict[str, Any]) -> dict[str, str]:
    """Parse entity mappings from form data."""
    from .const import CONF_ENTITY_MAPPINGS
    
    entity_mappings = {}
    for key, value in user_input.items():
        if key.startswith(f"{CONF_ENTITY_MAPPINGS}."):
            entity_type = key.replace(f"{CONF_ENTITY_MAPPINGS}.", "")
            # Only add non-empty values to mappings
            if value and value.strip():
                entity_mappings[entity_type] = value.strip()
    
    return entity_mappings