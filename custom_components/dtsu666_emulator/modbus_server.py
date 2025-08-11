"""Modbus server implementation for DTSU666 emulator."""
from __future__ import annotations

import asyncio
import logging
import struct
from typing import Any

from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.server import StartUdpServer
from pymodbus.payload import BinaryPayloadBuilder, Endian

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import REGISTER_MAP

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

        for register_name, entity_id in self.entity_mappings.items():
            if register_name not in REGISTER_MAP or not entity_id:
                continue

            try:
                # Get entity state
                state = self.hass.states.get(entity_id)
                if not state or state.state in ("unknown", "unavailable"):
                    _LOGGER.debug("Entity %s is unavailable", entity_id)
                    continue

                # Convert state to float
                try:
                    value = float(state.state)
                except (ValueError, TypeError):
                    _LOGGER.warning("Invalid numeric value for %s: %s", entity_id, state.state)
                    continue

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

    def _calculate_derived_values(self, values: dict[str, float]) -> dict[str, float]:
        """Calculate derived values from basic measurements."""
        derived = values.copy()

        # Calculate line-to-line voltages from line-to-neutral if needed
        if "voltage_l1" in values and "voltage_l2" in values:
            if "voltage_l1_l2" not in derived:
                derived["voltage_l1_l2"] = abs(values["voltage_l1"] - values["voltage_l2"])
        
        if "voltage_l2" in values and "voltage_l3" in values:
            if "voltage_l2_l3" not in derived:
                derived["voltage_l2_l3"] = abs(values["voltage_l2"] - values["voltage_l3"])
        
        if "voltage_l3" in values and "voltage_l1" in values:
            if "voltage_l3_l1" not in derived:
                derived["voltage_l3_l1"] = abs(values["voltage_l3"] - values["voltage_l1"])

        # Calculate currents from power and voltage if needed
        for phase in ["l1", "l2", "l3"]:
            power_key = f"power_{phase}"
            voltage_key = f"voltage_{phase}"
            current_key = f"current_{phase}"
            
            if (power_key in values and voltage_key in values 
                and current_key not in derived and values[voltage_key] > 0):
                derived[current_key] = abs(values[power_key] * 1000 / values[voltage_key])

        # Calculate power factor if reactive power is available
        if "power_total" in values and "reactive_power_total" in values:
            if "power_factor_total" not in derived:
                p = values["power_total"]
                q = values["reactive_power_total"]
                s = (p**2 + q**2)**0.5
                if s > 0:
                    derived["power_factor_total"] = p / s

        return derived