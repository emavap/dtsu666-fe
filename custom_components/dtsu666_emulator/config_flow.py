"""Config flow for DTSU666 Emulator integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.entity_registry import async_get

from .const import (
    CONF_ENTITY_MAPPINGS,
    CONF_HOST,
    CONF_PORT,
    CONF_SLAVE_ID,
    CONF_UPDATE_INTERVAL,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_SLAVE_ID,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    ENTITY_MAPPING_TYPES,
    REQUIRED_ENTITIES,
)

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DTSU666 Emulator."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self.data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate host and port
            if not self._is_valid_host(user_input[CONF_HOST]):
                errors[CONF_HOST] = "invalid_host"
            elif not (1 <= user_input[CONF_PORT] <= 65535):
                errors[CONF_PORT] = "invalid_port"
            elif not (1 <= user_input[CONF_SLAVE_ID] <= 247):
                errors[CONF_SLAVE_ID] = "invalid_slave_id"
            else:
                self.data = user_input
                return await self.async_step_entities()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=65535)
                ),
                vol.Required(CONF_SLAVE_ID, default=DEFAULT_SLAVE_ID): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=247)
                ),
                vol.Required(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=300)
                ),
            }),
            errors=errors,
        )

    async def async_step_entities(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle entity mapping step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Parse entity mappings from form data
            entity_mappings = {}
            for key, value in user_input.items():
                if key.startswith(f"{CONF_ENTITY_MAPPINGS}.") and value:
                    entity_type = key.replace(f"{CONF_ENTITY_MAPPINGS}.", "")
                    entity_mappings[entity_type] = value
            
            # Validate required entities are mapped
            missing_required = [
                entity_type for entity_type in REQUIRED_ENTITIES
                if not entity_mappings.get(entity_type)
            ]
            
            if missing_required:
                errors["base"] = "missing_required_entities"
                _LOGGER.error("Missing required entities: %s", missing_required)
            else:
                self.data[CONF_ENTITY_MAPPINGS] = entity_mappings
                return self.async_create_entry(
                    title="DTSU666 Emulator",
                    data=self.data,
                )

        # Get available sensor entities
        entity_registry = async_get(self.hass)
        sensor_entities = [
            entity.entity_id
            for entity in entity_registry.entities.values()
            if entity.entity_id.startswith("sensor.")
            and entity.device_class in ("power", "voltage", "current", "frequency", "energy")
        ]

        # Create schema for entity mapping
        entity_schema = {}
        for entity_type in ENTITY_MAPPING_TYPES:
            is_required = entity_type in REQUIRED_ENTITIES
            entity_schema[
                vol.Required(f"{CONF_ENTITY_MAPPINGS}.{entity_type}")
                if is_required
                else vol.Optional(f"{CONF_ENTITY_MAPPINGS}.{entity_type}")
            ] = selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor",
                    device_class=self._get_device_class_for_entity(entity_type),
                )
            )

        return self.async_show_form(
            step_id="entities",
            data_schema=vol.Schema(entity_schema),
            errors=errors,
            description_placeholders={
                "required_entities": ", ".join(REQUIRED_ENTITIES),
            },
        )

    @staticmethod
    def _is_valid_host(host: str) -> bool:
        """Validate host address."""
        if host in ("0.0.0.0", "localhost"):
            return True
        
        try:
            import ipaddress
            ipaddress.ip_address(host)
            return True
        except ValueError:
            return False

    @staticmethod
    def _get_device_class_for_entity(entity_type: str) -> str | None:
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

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self.data: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["network", "entities", "update_interval"],
        )

    async def async_step_network(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle network settings."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate settings
            if not self._is_valid_host(user_input[CONF_HOST]):
                errors[CONF_HOST] = "invalid_host"
            elif not (1 <= user_input[CONF_PORT] <= 65535):
                errors[CONF_PORT] = "invalid_port"
            elif not (1 <= user_input[CONF_SLAVE_ID] <= 247):
                errors[CONF_SLAVE_ID] = "invalid_slave_id"
            else:
                # Update config entry data
                new_data = dict(self.config_entry.data)
                new_data.update(user_input)
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=new_data
                )
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="network",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_HOST,
                    default=self.config_entry.data.get(CONF_HOST, DEFAULT_HOST),
                ): str,
                vol.Required(
                    CONF_PORT,
                    default=self.config_entry.data.get(CONF_PORT, DEFAULT_PORT),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
                vol.Required(
                    CONF_SLAVE_ID,
                    default=self.config_entry.data.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=247)),
            }),
            errors=errors,
        )

    async def async_step_entities(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle entity mapping."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Parse entity mappings
            entity_mappings = {}
            for key, value in user_input.items():
                if key.startswith(f"{CONF_ENTITY_MAPPINGS}.") and value:
                    entity_type = key.replace(f"{CONF_ENTITY_MAPPINGS}.", "")
                    entity_mappings[entity_type] = value
            
            # Validate required entities
            missing_required = [
                entity_type for entity_type in REQUIRED_ENTITIES
                if not entity_mappings.get(entity_type)
            ]
            
            if missing_required:
                errors["base"] = "missing_required_entities"
            else:
                # Update config entry data
                new_data = dict(self.config_entry.data)
                new_data[CONF_ENTITY_MAPPINGS] = entity_mappings
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=new_data
                )
                return self.async_create_entry(title="", data={})

        # Create schema for entity mapping
        current_mappings = self.config_entry.data.get(CONF_ENTITY_MAPPINGS, {})
        entity_schema = {}
        for entity_type in ENTITY_MAPPING_TYPES:
            is_required = entity_type in REQUIRED_ENTITIES
            current_value = current_mappings.get(entity_type, "")
            
            entity_schema[
                vol.Required(f"{CONF_ENTITY_MAPPINGS}.{entity_type}", default=current_value)
                if is_required
                else vol.Optional(f"{CONF_ENTITY_MAPPINGS}.{entity_type}", default=current_value)
            ] = selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor",
                    device_class=self._get_device_class_for_entity(entity_type),
                )
            )

        return self.async_show_form(
            step_id="entities",
            data_schema=vol.Schema(entity_schema),
            errors=errors,
            description_placeholders={
                "required_entities": ", ".join(REQUIRED_ENTITIES),
            },
        )

    async def async_step_update_interval(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle update interval."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="update_interval",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_UPDATE_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_UPDATE_INTERVAL, 
                        self.config_entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=300)),
            }),
        )

    @staticmethod
    def _is_valid_host(host: str) -> bool:
        """Validate host address."""
        if host in ("0.0.0.0", "localhost"):
            return True
        
        try:
            import ipaddress
            ipaddress.ip_address(host)
            return True
        except ValueError:
            return False

    @staticmethod
    def _get_device_class_for_entity(entity_type: str) -> str | None:
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