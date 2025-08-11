"""Modbus server implementation for DTSU666 emulator."""
from __future__ import annotations

import asyncio
import logging
import threading

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
        self._state_lock = threading.RLock()

    async def start(self) -> bool:
        """Start the Modbus server."""
        try:
            # Validate configuration
            if not self._validate_configuration():
                return False
                
            # Initialize data block with zeros
            self._data_block = ModbusSequentialDataBlock(0, [0] * 10000)
            
            # Setup device identification
            identity = self._create_device_identification()

            # Create server context
            slave_context = ModbusSlaveContext(
                hr=self._data_block,
                ir=self._data_block,
            )
            context = ModbusServerContext(slaves={self.slave_id: slave_context}, single=False)

            # Start the server
            self._running = True
            
            # Create server task with error handling
            self._server_task = asyncio.create_task(self._run_server_with_recovery(context, identity))

            # Start periodic updates with error handling
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
            await self._cleanup_on_error()
            return False
            
    def _validate_configuration(self) -> bool:
        """Validate server configuration."""
        try:
            # Check port availability
            if not (1 <= self.port <= 65535):
                _LOGGER.error("Invalid port number: %d", self.port)
                return False
                
            # Check slave ID
            if not (1 <= self.slave_id <= 247):
                _LOGGER.error("Invalid slave ID: %d", self.slave_id)
                return False
                
            # Check update interval
            if not (1 <= self.update_interval <= 300):
                _LOGGER.error("Invalid update interval: %d", self.update_interval)
                return False
                
            return True
            
        except Exception as ex:
            _LOGGER.error("Configuration validation failed: %s", ex)
            return False
            
    def _create_device_identification(self) -> ModbusDeviceIdentification:
        """Create Modbus device identification."""
        identity = ModbusDeviceIdentification()
        identity.VendorName = "CHINT"
        identity.ProductCode = "DTSU666"
        identity.VendorUrl = "http://www.chint.com"
        identity.ProductName = "DTSU666 Energy Meter"
        identity.ModelName = "DTSU666-FE"
        identity.MajorMinorRevision = "1.0"
        return identity
        
    async def _run_server_with_recovery(
        self, 
        context: ModbusServerContext, 
        identity: ModbusDeviceIdentification
    ) -> None:
        """Run the Modbus server with automatic recovery."""
        max_retries = 3
        retry_count = 0
        
        while self._running and retry_count < max_retries:
            try:
                await StartUdpServer(
                    context=context,
                    identity=identity,
                    address=(self.host, self.port),
                    custom_functions=[],
                    defer_start=False,
                )
                break  # Server started successfully
                
            except OSError as ex:
                retry_count += 1
                if "Address already in use" in str(ex):
                    _LOGGER.warning(
                        "Port %d is busy, retrying in 2 seconds (attempt %d/%d)",
                        self.port, retry_count, max_retries
                    )
                    await asyncio.sleep(2)
                else:
                    _LOGGER.error("Network error starting server: %s", ex)
                    break
                    
            except Exception as ex:
                _LOGGER.error("Unexpected error starting server: %s", ex)
                break
                
        if retry_count >= max_retries:
            _LOGGER.error("Failed to start server after %d attempts", max_retries)
            self._running = False
            
    async def _cleanup_on_error(self) -> None:
        """Clean up resources on startup error."""
        self._running = False
        
        if self._update_task:
            self._update_task.cancel()
            self._update_task = None
            
        if self._server_task:
            self._server_task.cancel() 
            self._server_task = None

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
        error_count = 0
        max_errors = 10
        backoff_delay = self.update_interval
        
        while self._running:
            try:
                await self._update_registers()
                # Reset error tracking on successful update
                error_count = 0
                backoff_delay = self.update_interval
                await asyncio.sleep(self.update_interval)
                
            except asyncio.CancelledError:
                _LOGGER.debug("Periodic update task cancelled")
                break
                
            except Exception as ex:
                error_count += 1
                _LOGGER.error("Error updating registers (attempt %d/%d): %s", 
                            error_count, max_errors, ex)
                
                # Implement exponential backoff for repeated errors
                if error_count >= max_errors:
                    _LOGGER.error("Too many consecutive errors, stopping register updates")
                    break
                    
                backoff_delay = min(backoff_delay * 1.5, 60)  # Max 60 second delay
                _LOGGER.warning("Using backoff delay of %.1f seconds", backoff_delay)
                
                try:
                    await asyncio.sleep(backoff_delay)
                except asyncio.CancelledError:
                    break

    async def _update_registers(self) -> None:
        """Update Modbus registers with current entity values."""
        if not self._data_block:
            return

        # Check if any required entities are unavailable
        meter_should_fail = self._check_meter_health()
        
        with self._state_lock:
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
                    await self._restore_meter_values()

        # Get all values (mapped + defaults + calculated)
        all_values = self._get_all_register_values()
        
        # Update all registers
        for register_name, value in all_values.items():
            self._update_single_register(register_name, value)
    
    async def _restore_meter_values(self) -> None:
        """Restore meter values after recovery from failure."""
        _LOGGER.debug("Restoring meter values after failure recovery")
        # Force immediate update of all register values
        all_values = self._get_all_register_values()
        for register_name, value in all_values.items():
            self._update_single_register(register_name, value)

    def _update_single_register(self, register_name: str, value: float) -> None:
        """Update a single Modbus register with proper scaling and bounds checking."""
        if not self._data_block or register_name not in REGISTER_MAP:
            return

        try:
            register_info = REGISTER_MAP[register_name]
            address = register_info["addr"]
            scale = register_info["scale"]

            # Apply scaling: raw_value = actual_value / scale
            # Example: 230V with scale 0.1 becomes 2300 in register
            raw_value = value / scale if scale != 0 else 0
            
            # Convert to integer and handle bounds
            scaled_value = int(round(raw_value))
            
            # Handle negative values with two's complement for 16-bit signed
            if scaled_value < 0:
                scaled_value = max(-32768, scaled_value)  # Min signed 16-bit
                scaled_value = (1 << 16) + scaled_value
            else:
                scaled_value = min(32767, scaled_value)  # Max signed 16-bit
            
            # Ensure final value is in 16-bit unsigned range
            scaled_value = scaled_value & 0xFFFF

            # Write to Modbus register
            self._data_block.setValues(address, [scaled_value])
            
            with self._state_lock:
                self._current_values[register_name] = value
                self._raw_register_values[register_name] = scaled_value
            
            _LOGGER.debug(
                "Updated register %s (0x%04X): %.3f -> %d (scale: %.3f)",
                register_name, address, value, scaled_value, scale
            )

        except Exception as ex:
            _LOGGER.error("Error updating register %s with value %s: %s", 
                         register_name, value, ex)

    def _check_meter_health(self) -> bool:
        """Check if meter should fail due to unavailable required entities."""
        for required_entity_type in REQUIRED_ENTITIES:
            entity_id = self.entity_mappings.get(required_entity_type)
            if not entity_id:
                _LOGGER.debug("Required entity %s is not mapped", required_entity_type)
                return True
                
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
            
            with self._state_lock:
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

        # Get reference values for calculations
        reference_voltage = derived.get("voltage_l1", 0.0)
        total_power = derived.get("power_total", 0.0)
        
        # Calculate voltage-related values
        if reference_voltage > 0:
            self._calculate_voltage_derivatives(derived, reference_voltage)
        
        # Calculate power-related values  
        if total_power > 0:
            self._calculate_power_derivatives(derived, total_power)
            
        # Calculate currents from power and voltage
        self._calculate_currents(derived)
        
        # Calculate power factor
        self._calculate_power_factor(derived)

        return derived

    def _calculate_voltage_derivatives(self, derived: dict[str, float], reference_voltage: float) -> None:
        """Calculate voltage derivatives using reference voltage."""
        line_to_line_voltage = reference_voltage * 1.732  # √3 for 3-phase
        
        # Set line-to-line voltages if not mapped
        for ll_voltage in ["voltage_l1_l2", "voltage_l2_l3", "voltage_l3_l1"]:
            if derived.get(ll_voltage, 0) == 0:
                derived[ll_voltage] = line_to_line_voltage
        
        # Set other phase voltages to reference if not mapped  
        for phase_voltage in ["voltage_l2", "voltage_l3"]:
            if derived.get(phase_voltage, 0) == 0:
                derived[phase_voltage] = reference_voltage

    def _calculate_power_derivatives(self, derived: dict[str, float], total_power: float) -> None:
        """Calculate individual phase powers from total."""
        phase_power = total_power / 3  # Equal distribution across phases
        
        for phase in ["l1", "l2", "l3"]:
            power_key = f"power_{phase}"
            if derived.get(power_key, 0) == 0:
                derived[power_key] = phase_power

    def _calculate_currents(self, derived: dict[str, float]) -> None:
        """Calculate currents from power and voltage."""
        for phase in ["l1", "l2", "l3"]:
            power = derived.get(f"power_{phase}", 0)
            voltage = derived.get(f"voltage_{phase}", 0)
            current_key = f"current_{phase}"
            
            if power > 0 and voltage > 0 and derived.get(current_key, 0) == 0:
                try:
                    derived[current_key] = (power * 1000) / voltage
                except ZeroDivisionError:
                    _LOGGER.warning("Division by zero calculating current for %s", phase)
                    derived[current_key] = 0

    def _calculate_power_factor(self, derived: dict[str, float]) -> None:
        """Calculate power factor from active and reactive power."""
        active_power = derived.get("power_total", 0)
        reactive_power = derived.get("reactive_power_total", 0)
        
        if active_power > 0 and derived.get("power_factor_total", 0) == 0:
            if reactive_power != 0:
                apparent_power = (active_power**2 + reactive_power**2)**0.5
                if apparent_power > 0:
                    derived["power_factor_total"] = min(1.0, abs(active_power) / apparent_power)
                else:
                    derived["power_factor_total"] = 1.0
            else:
                derived["power_factor_total"] = 1.0

    def get_register_value(self, register_name: str) -> float | None:
        """Get the current scaled value for a register."""
        with self._state_lock:
            return self._current_values.get(register_name)

    def get_raw_register_value(self, register_name: str) -> int | None:
        """Get the raw register value (as stored in Modbus)."""
        with self._state_lock:
            return self._raw_register_values.get(register_name)

    @property
    def is_running(self) -> bool:
        """Check if the server is running."""
        return self._running

    @property
    def is_meter_failed(self) -> bool:
        """Check if meter is in failed state."""
        with self._state_lock:
            return self._meter_failed