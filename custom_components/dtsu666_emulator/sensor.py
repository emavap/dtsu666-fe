"""Sensor platform for DTSU666 Emulator."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, REGISTER_MAP
from .modbus_server import DTSU666ModbusServer

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up DTSU666 Emulator sensor entities."""
    try:
        _LOGGER.info("Setting up DTSU666 sensor entities for entry %s", config_entry.entry_id)
        
        server: DTSU666ModbusServer = hass.data[DOMAIN][config_entry.entry_id]
        entity_mappings = config_entry.data.get("entity_mappings", {})
        
        _LOGGER.info("Found %d entity mappings: %s", len(entity_mappings), list(entity_mappings.keys()))
        
        # Create diagnostic sensors for ALL registers (mapped + defaults)
        sensors = []
        for register_name in REGISTER_MAP.keys():
            try:
                source_entity = entity_mappings.get(register_name, "default")
                sensor = DTSU666RegisterSensor(
                    server=server,
                    config_entry=config_entry,
                    register_name=register_name,
                    source_entity=source_entity,
                )
                sensors.append(sensor)
            except Exception as ex:
                _LOGGER.error("Failed to create sensor for register %s: %s", register_name, ex, exc_info=True)
        
        # Add server status sensor
        sensors.append(
            DTSU666ServerStatusSensor(
                server=server,
                config_entry=config_entry,
            )
        )
        
        # Add summary sensor for key values
        sensors.append(
            DTSU666SummarySensor(
                server=server,
                config_entry=config_entry,
            )
        )
        
        _LOGGER.info("Adding %d sensors to Home Assistant", len(sensors))
        async_add_entities(sensors, True)
        _LOGGER.info("Successfully added DTSU666 sensor entities")
        
    except Exception as ex:
        _LOGGER.error("Failed to set up DTSU666 sensor platform: %s", ex, exc_info=True)
        raise


class DTSU666RegisterSensor(SensorEntity):
    """Sensor that shows the actual register value being sent via Modbus."""

    def __init__(
        self,
        server: DTSU666ModbusServer,
        config_entry: ConfigEntry,
        register_name: str,
        source_entity: str,
    ) -> None:
        """Initialize the sensor."""
        self._server = server
        self._config_entry = config_entry
        self._register_name = register_name
        self._source_entity = source_entity
        self._register_info = REGISTER_MAP[register_name]
        
        # Generate unique ID
        self._attr_unique_id = f"{config_entry.entry_id}_{register_name}_register"
        friendly_name = self._get_friendly_name(register_name)
        self._attr_name = f"DTSU666 {friendly_name}"
        
        self._attr_entity_registry_enabled_default = True
        
        # Set device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name="DTSU666 Emulator",
            manufacturer="CHINT (Emulated)",
            model="DTSU666-FE",
            sw_version="1.0.0",
        )
        
        # Set sensor properties based on register type
        self._setup_sensor_properties()

    def _get_friendly_name(self, register_name: str) -> str:
        """Get a friendly display name for the register."""
        name_map = {
            "voltage_l1": "Voltage L1",
            "voltage_l2": "Voltage L2", 
            "voltage_l3": "Voltage L3",
            "voltage_l1_l2": "Voltage L1-L2",
            "voltage_l2_l3": "Voltage L2-L3",
            "voltage_l3_l1": "Voltage L3-L1",
            "current_l1": "Current L1",
            "current_l2": "Current L2",
            "current_l3": "Current L3",
            "current_neutral": "Current Neutral",
            "power_l1": "Power L1",
            "power_l2": "Power L2",
            "power_l3": "Power L3",
            "power_total": "Total Power",
            "reactive_power_l1": "Reactive Power L1",
            "reactive_power_l2": "Reactive Power L2",
            "reactive_power_l3": "Reactive Power L3",
            "reactive_power_total": "Total Reactive Power",
            "power_factor_l1": "Power Factor L1",
            "power_factor_l2": "Power Factor L2",
            "power_factor_l3": "Power Factor L3",
            "power_factor_total": "Total Power Factor",
            "energy_import_total": "Total Energy Import",
            "energy_export_total": "Total Energy Export",
            "frequency": "Grid Frequency",
        }
        return name_map.get(register_name, register_name.replace('_', ' ').title())

    def _setup_sensor_properties(self) -> None:
        """Set up sensor properties based on register type."""
        unit = self._register_info.get("unit", "")
        
        # Set device class and unit
        if "voltage" in self._register_name:
            self._attr_device_class = SensorDeviceClass.VOLTAGE
            self._attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
        elif "current" in self._register_name:
            self._attr_device_class = SensorDeviceClass.CURRENT
            self._attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
        elif "power" in self._register_name and "reactive" not in self._register_name:
            self._attr_device_class = SensorDeviceClass.POWER
            self._attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
        elif "reactive_power" in self._register_name:
            self._attr_device_class = SensorDeviceClass.REACTIVE_POWER
            self._attr_native_unit_of_measurement = "kVAr"
        elif "energy" in self._register_name:
            self._attr_device_class = SensorDeviceClass.ENERGY
            self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        elif "frequency" in self._register_name:
            self._attr_device_class = SensorDeviceClass.FREQUENCY
            self._attr_native_unit_of_measurement = UnitOfFrequency.HERTZ
        elif "power_factor" in self._register_name:
            self._attr_device_class = SensorDeviceClass.POWER_FACTOR
            self._attr_native_unit_of_measurement = None
        else:
            self._attr_native_unit_of_measurement = unit
        
        # Set state class for numeric sensors
        if self._attr_state_class is None and "energy" not in self._register_name:
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return the current register value."""
        try:
            value = self._server.get_register_value(self._register_name)
            if value is None:
                return 0.0  # Return 0 instead of None for better display
            return value
        except Exception as ex:
            _LOGGER.error("Error getting register value for %s: %s", self._register_name, ex)
            return 0.0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        try:
            raw_value = self._server.get_raw_register_value(self._register_name)
            current_value = self._server.get_register_value(self._register_name)
        except Exception as ex:
            _LOGGER.error("Error getting register values for %s: %s", self._register_name, ex)
            raw_value = None
            current_value = None
            
        attributes = {
            "register_address": f"0x{self._register_info['addr']:04X}",
            "register_scale": self._register_info["scale"],
            "source_entity": self._source_entity if self._source_entity != "default" else "Default Value",
            "raw_register_value": raw_value,
            "modbus_hex": f"0x{raw_value:04X}" if raw_value is not None else None,
        }
        
        # Add calculated vs mapped information
        if self._source_entity == "default":
            attributes["data_source"] = "Calculated/Default"
        else:
            attributes["data_source"] = "Mapped Entity"
            # Try to get the actual entity state
            try:
                if self.hass and self._source_entity != "default":
                    state = self.hass.states.get(self._source_entity)
                    if state:
                        attributes["source_entity_state"] = state.state
                        attributes["source_entity_unit"] = state.attributes.get("unit_of_measurement", "")
            except Exception:
                pass
                
        return attributes

    @property
    def available(self) -> bool:
        """Return if sensor is available."""
        try:
            return self._server.is_running
        except Exception as ex:
            _LOGGER.error("Error checking availability for %s: %s", self._register_name, ex)
            return False


class DTSU666ServerStatusSensor(SensorEntity):
    """Sensor that shows the server status and connection info."""

    def __init__(
        self,
        server: DTSU666ModbusServer,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        self._server = server
        self._config_entry = config_entry
        
        self._attr_unique_id = f"{config_entry.entry_id}_server_status"
        self._attr_name = "DTSU666 Server Status"
        self._attr_icon = "mdi:server-network"
        
        self._attr_entity_registry_enabled_default = True
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name="DTSU666 Emulator",
            manufacturer="CHINT (Emulated)",
            model="DTSU666-FE", 
            sw_version="1.0.0",
        )

    @property
    def native_value(self) -> str:
        """Return the server status."""
        if not self._server.is_running:
            return "stopped"
        elif self._server.is_meter_failed:
            return "meter_failed"
        else:
            return "running"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return server connection attributes."""
        entity_mappings = self._config_entry.data.get("entity_mappings", {})
        return {
            "host": self._config_entry.data.get("host"),
            "port": self._config_entry.data.get("port"),
            "slave_id": self._config_entry.data.get("slave_id"),
            "update_interval": self._config_entry.options.get(
                "update_interval", 
                self._config_entry.data.get("update_interval")
            ),
            "mapped_entities": len(entity_mappings),
            "meter_failed": self._server.is_meter_failed,
            "required_entities_status": self._get_required_entities_status(),
        }

    def _get_required_entities_status(self) -> dict[str, str]:
        """Get status of required entities."""
        try:
            entity_mappings = self._config_entry.data.get("entity_mappings", {})
            status = {}
            
            from .const import REQUIRED_ENTITIES
            for required_entity_type in REQUIRED_ENTITIES:
                try:
                    entity_id = entity_mappings.get(required_entity_type)
                    if not entity_id:
                        status[required_entity_type] = "not_mapped"
                        continue
                        
                    state = self.hass.states.get(entity_id)
                    if not state:
                        status[required_entity_type] = "entity_not_found"
                    elif state.state in ("unknown", "unavailable"):
                        status[required_entity_type] = "unavailable"
                    else:
                        try:
                            float(state.state)
                            status[required_entity_type] = "ok"
                        except (ValueError, TypeError):
                            status[required_entity_type] = "invalid_value"
                            
                except Exception as ex:
                    _LOGGER.error("Error checking status for entity %s: %s", required_entity_type, ex)
                    status[required_entity_type] = "error"
            
            return status
            
        except Exception as ex:
            _LOGGER.error("Error getting required entities status: %s", ex)
            return {}

    @property
    def available(self) -> bool:
        """Return if sensor is available."""
        return True


class DTSU666SummarySensor(SensorEntity):
    """Sensor that shows a summary of key Modbus register values."""

    def __init__(
        self,
        server: DTSU666ModbusServer,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        self._server = server
        self._config_entry = config_entry
        
        self._attr_unique_id = f"{config_entry.entry_id}_register_summary"
        self._attr_name = "DTSU666 Register Summary"
        self._attr_icon = "mdi:chart-box"
        
        self._attr_entity_registry_enabled_default = True
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name="DTSU666 Emulator",
            manufacturer="CHINT (Emulated)",
            model="DTSU666-FE", 
            sw_version="1.0.0",
        )

    @property
    def native_value(self) -> str:
        """Return the summary status."""
        try:
            total_registers = len(REGISTER_MAP)
            active_registers = len([v for v in [
                self._server.get_register_value(name) for name in REGISTER_MAP.keys()
            ] if v is not None and v != 0])
            
            return f"{active_registers}/{total_registers} registers active"
        except Exception as ex:
            _LOGGER.error("Error getting summary: %s", ex)
            return "Error"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return summary of all register values."""
        try:
            summary = {}
            key_registers = ["power_total", "voltage_l1", "frequency", "current_l1", "energy_import_total", "energy_export_total"]
            
            for register_name in key_registers:
                try:
                    value = self._server.get_register_value(register_name)
                    raw_value = self._server.get_raw_register_value(register_name)
                    
                    if value is not None:
                        unit = REGISTER_MAP[register_name].get("unit", "")
                        summary[f"{register_name}_value"] = f"{value:.3f} {unit}".strip()
                        summary[f"{register_name}_raw"] = raw_value
                        summary[f"{register_name}_address"] = f"0x{REGISTER_MAP[register_name]['addr']:04X}"
                        
                except Exception as ex:
                    _LOGGER.debug("Error getting register %s: %s", register_name, ex)
                    summary[f"{register_name}_value"] = "N/A"
            
            # Add non-zero register count
            all_values = {}
            for register_name in REGISTER_MAP.keys():
                try:
                    value = self._server.get_register_value(register_name)
                    if value is not None and value != 0:
                        all_values[register_name] = value
                except Exception:
                    pass
                    
            summary["active_registers"] = list(all_values.keys())
            summary["total_registers"] = len(REGISTER_MAP)
            summary["meter_status"] = "failed" if self._server.is_meter_failed else "running"
            
            return summary
            
        except Exception as ex:
            _LOGGER.error("Error building register summary: %s", ex)
            return {"error": str(ex)}

    @property
    def available(self) -> bool:
        """Return if sensor is available."""
        return self._server.is_running


