"""Sensor platform for DTSU666 Emulator."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
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
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, REGISTER_MAP
from .modbus_server import DTSU666ModbusServer

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up DTSU666 Emulator sensor entities."""
    server: DTSU666ModbusServer = hass.data[DOMAIN][config_entry.entry_id]
    entity_mappings = config_entry.data.get("entity_mappings", {})
    
    # Create diagnostic sensors for all mapped registers
    sensors = []
    for register_name, entity_id in entity_mappings.items():
        if register_name in REGISTER_MAP and entity_id:
            sensors.append(
                DTSU666RegisterSensor(
                    server=server,
                    config_entry=config_entry,
                    register_name=register_name,
                    source_entity=entity_id,
                )
            )
    
    # Add server status sensor
    sensors.append(
        DTSU666ServerStatusSensor(
            server=server,
            config_entry=config_entry,
        )
    )
    
    async_add_entities(sensors)


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
        self._attr_name = f"DTSU666 {register_name.replace('_', ' ').title()} Register"
        
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
            self._attr_native_unit_of_measurement = UnitOfPower.WATT
        elif "reactive_power" in self._register_name:
            self._attr_device_class = SensorDeviceClass.REACTIVE_POWER
            self._attr_native_unit_of_measurement = "VAr"
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
        return self._server.get_register_value(self._register_name)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        return {
            "register_address": f"0x{self._register_info['addr']:04X}",
            "register_scale": self._register_info["scale"],
            "source_entity": self._source_entity,
            "raw_register_value": self._server.get_raw_register_value(self._register_name),
        }

    @property
    def available(self) -> bool:
        """Return if sensor is available."""
        return self._server.is_running


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
        if self._server.is_running:
            return "running"
        return "stopped"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return server connection attributes."""
        return {
            "host": self._config_entry.data.get("host"),
            "port": self._config_entry.data.get("port"),
            "slave_id": self._config_entry.data.get("slave_id"),
            "update_interval": self._config_entry.options.get(
                "update_interval", 
                self._config_entry.data.get("update_interval")
            ),
            "mapped_entities": len(self._config_entry.data.get("entity_mappings", {})),
        }

    @property
    def available(self) -> bool:
        """Return if sensor is available."""
        return True