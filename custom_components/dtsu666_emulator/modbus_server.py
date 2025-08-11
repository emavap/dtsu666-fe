"""Modbus server implementation for DTSU666 emulator."""
from __future__ import annotations

import asyncio
import logging

from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.server import StartUdpServer

from homeassistant.core import HomeAssistant

from .const import REGISTER_MAP, DEFAULT_VALUES, REQUIRED_ENTITIES

_LOGGER = logging.getLogger(__name__)


class DTSU666ModbusServer:
    """Modbus server that emulates DTSU666 smart meter."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        slave_id: int,
        entity_mappings: dict[str, str],
        update_interval: int,
    ) -> None:
        """Initialize the Modbus server."""
        self.hass = hass
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.entity_mappings = entity_mappings
        self.update_interval = update_interval
        self._server_task: asyncio.Task | None = None
        self._update_task: asyncio.Task | None = None
        self._data_block: ModbusSequentialDataBlock | None = None
        self._running = False
        self._current_values: dict[str, float] = {}
        self._raw_register_values: dict[str, int] = {}
        self._meter_failed = False
        self._server = None

    async def start(self) -> bool:
        """Start the Modbus server."""
        try:
            # Initialize data block with zeros
            self._data_block = ModbusSequentialDataBlock(0, [0] * 10000)
            
            # Setup device identification
            identity = ModbusDeviceIdentification()
            identity.VendorName = "CHINT"
            identity.ProductCode = "DTSU666"
            identity.VendorUrl = "http://www.chint.com"
            identity.ProductName = "DTSU666 Energy Meter"
            identity.ModelName = "DTSU666-FE"
            identity.MajorMinorRevision = "1.0"

            # Create server context
            slave_context = ModbusSlaveContext(
                hr=self._data_block,
                ir=self._data_block,
            )
            context = ModbusServerContext(slaves={self.slave_id: slave_context}, single=False)

            # Start the server
            self._running = True
            
            # Create server task
            async def run_server():
                await StartUdpServer(
                    context=context,
                    identity=identity,
                    address=(self.host, self.port),
                    custom_functions=[],
                    defer_start=False,
                )
            
            self._server_task = asyncio.create_task(run_server())

            # Start periodic updates
            self._update_task = asyncio.create_task(self._periodic_update())
            
            _LOGGER.info(
                "DTSU666 Modbus server started on %s:%d (slave ID: %d)",
                self.host,
                self.port,
                self.slave_id,
            )
            return True

        except Exception as ex:
            _LOGGER.error("Failed to start Modbus server: %s", ex)
            return False

    async def stop(self) -> None:
        """Stop the Modbus server."""
        self._running = False
        
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass

        if self._server_task:
            self._server_task.cancel()
            try:
                await self._server_task
            except asyncio.CancelledError:
                pass

        _LOGGER.info("DTSU666 Modbus server stopped")

    async def _periodic_update(self) -> None:
        """Periodically update Modbus registers from HA entities."""
        while self._running:
            try:
                await self._update_registers()
                await asyncio.sleep(self.update_interval)
            except asyncio.CancelledError:
                break
            except Exception as ex:
                _LOGGER.error("Error updating registers: %s", ex)
                await asyncio.sleep(self.update_interval)

    async def _update_registers(self) -> None:
        """Update Modbus registers with current entity values."""
        if not self._data_block:
            return

        # Check if any required entities are unavailable
        meter_should_fail = self._check_meter_health()
        
        if meter_should_fail:
            if not self._meter_failed:
                _LOGGER.warning("Meter simulation failed - required entities unavailable")
                self._meter_failed = True
                # Stop responding to Modbus requests by clearing all registers
                await self._simulate_meter_failure()
            return
        else:
            if self._meter_failed:
                _LOGGER.info("Meter simulation recovered - entities now available")
                self._meter_failed = False

        # Get all values (mapped + defaults + calculated)
        all_values = self._get_all_register_values()
        
        # Update all registers
        for register_name, value in all_values.items():
            if register_name not in REGISTER_MAP:
                continue

            try:
                # Get register info
                register_info = REGISTER_MAP[register_name]
                address = register_info["addr"]
                scale = register_info["scale"]

                # Scale and convert value
                scaled_value = int(value / scale)
                
                # Handle negative values (two's complement)
                if scaled_value < 0:
                    scaled_value = (1 << 16) + scaled_value

                # Ensure value fits in 16-bit register
                scaled_value = max(0, min(65535, scaled_value))

                # Write to register
                self._data_block.setValues(address, [scaled_value])
                
                # Store current values for sensors
                self._current_values[register_name] = value
                self._raw_register_values[register_name] = scaled_value
                
                _LOGGER.debug(
                    "Updated register %s (0x%04X): %s -> %d (scale: %s)",
                    register_name,
                    address,
                    value,
                    scaled_value,
                    scale,
                )

            except Exception as ex:
                _LOGGER.error("Error updating register %s: %s", register_name, ex)

    def _check_meter_health(self) -> bool:
        """Check if meter should fail due to unavailable required entities."""
        for required_entity_type in REQUIRED_ENTITIES:
            entity_id = self.entity_mappings.get(required_entity_type)
            if not entity_id:
                continue
                
            state = self.hass.states.get(entity_id)
            if not state or state.state in ("unknown", "unavailable"):
                _LOGGER.debug("Required entity %s (%s) is unavailable", required_entity_type, entity_id)
                return True
                
            try:
                float(state.state)
            except (ValueError, TypeError):
                _LOGGER.debug("Required entity %s (%s) has invalid value: %s", 
                            required_entity_type, entity_id, state.state)
                return True
        
        return False

    async def _simulate_meter_failure(self) -> None:
        """Simulate meter failure by clearing all registers or stopping server."""
        if self._data_block:
            # Clear all registers to simulate meter not responding
            for register_info in REGISTER_MAP.values():
                address = register_info["addr"]
                self._data_block.setValues(address, [0])
            
            # Clear stored values
            self._current_values.clear()
            self._raw_register_values.clear()

    def _get_all_register_values(self) -> dict[str, float]:
        """Get all register values combining mapped entities, defaults, and calculated values."""
        values = {}
        
        # Start with default values
        values.update(DEFAULT_VALUES)
        
        # Override with mapped entity values where available
        for register_name, entity_id in self.entity_mappings.items():
            if not entity_id or register_name not in REGISTER_MAP:
                continue
                
            state = self.hass.states.get(entity_id)
            if state and state.state not in ("unknown", "unavailable"):
                try:
                    value = float(state.state)
                    values[register_name] = value
                    _LOGGER.debug("Using mapped value for %s: %s from %s", register_name, value, entity_id)
                except (ValueError, TypeError):
                    _LOGGER.warning("Invalid numeric value for %s: %s", entity_id, state.state)
        
        # Calculate derived values
        values = self._calculate_derived_values(values)
        
        return values

    def _calculate_derived_values(self, values: dict[str, float]) -> dict[str, float]:
        """Calculate derived values from basic measurements."""
        derived = values.copy()

        # Use mapped voltage_l1 as reference for calculations if available
        reference_voltage = derived.get("voltage_l1", 230.0)  # Default to 230V if not mapped
        
        # Calculate line-to-line voltages using reference voltage if needed
        if derived.get("voltage_l1_l2", 0) == 0 and reference_voltage > 0:
            derived["voltage_l1_l2"] = reference_voltage * 1.732  # √3 for 3-phase
        if derived.get("voltage_l2_l3", 0) == 0 and reference_voltage > 0:
            derived["voltage_l2_l3"] = reference_voltage * 1.732
        if derived.get("voltage_l3_l1", 0) == 0 and reference_voltage > 0:
            derived["voltage_l3_l1"] = reference_voltage * 1.732

        # Set other phase voltages to reference if not mapped
        if derived.get("voltage_l2", 0) == 0 and reference_voltage > 0:
            derived["voltage_l2"] = reference_voltage
        if derived.get("voltage_l3", 0) == 0 and reference_voltage > 0:
            derived["voltage_l3"] = reference_voltage

        # Calculate phase powers from total if not mapped
        total_power = derived.get("power_total", 0)
        if total_power > 0:
            if derived.get("power_l1", 0) == 0:
                derived["power_l1"] = total_power / 3  # Equal distribution
            if derived.get("power_l2", 0) == 0:
                derived["power_l2"] = total_power / 3
            if derived.get("power_l3", 0) == 0:
                derived["power_l3"] = total_power / 3

        # Calculate currents from power and voltage
        for phase in ["l1", "l2", "l3"]:
            power_key = f"power_{phase}"
            voltage_key = f"voltage_{phase}"
            current_key = f"current_{phase}"
            
            power = derived.get(power_key, 0)
            voltage = derived.get(voltage_key, 0)
            
            if power > 0 and voltage > 0 and derived.get(current_key, 0) == 0:
                # Convert kW to W for calculation
                derived[current_key] = (power * 1000) / voltage

        # Calculate power factor from power and reactive power
        active_power = derived.get("power_total", 0)
        reactive_power = derived.get("reactive_power_total", 0)
        
        if active_power > 0 and derived.get("power_factor_total", 0) == 0:
            if reactive_power > 0:
                apparent_power = (active_power**2 + reactive_power**2)**0.5
                derived["power_factor_total"] = active_power / apparent_power
            else:
                derived["power_factor_total"] = 1.0  # Unity power factor if no reactive power

        return derived

    def get_register_value(self, register_name: str) -> float | None:
        """Get the current scaled value for a register."""
        return self._current_values.get(register_name)

    def get_raw_register_value(self, register_name: str) -> int | None:
        """Get the raw register value (as stored in Modbus)."""
        return self._raw_register_values.get(register_name)

    @property
    def is_running(self) -> bool:
        """Check if the server is running."""
        return self._running

    @property
    def is_meter_failed(self) -> bool:
        """Check if meter is in failed state."""
        return self._meter_failed