"""Constants for DTSU666 Emulator integration."""
from __future__ import annotations

DOMAIN = "dtsu666_emulator"

# Configuration keys
CONF_HOST = "host"
CONF_PORT = "port"
CONF_SLAVE_ID = "slave_id"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_ENTITY_MAPPINGS = "entity_mappings"

# Default values
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 5020
DEFAULT_SLAVE_ID = 11
DEFAULT_UPDATE_INTERVAL = 5

# Modbus register mappings based on DTSU666 specification
# Addresses and scales from jsphuebner/dtsu666-Emulator
REGISTER_MAP = {
    # Voltage measurements (Line-to-Line)
    "voltage_l1_l2": {"addr": 0x1836, "scale": 0.1, "unit": "V"},
    "voltage_l2_l3": {"addr": 0x1838, "scale": 0.1, "unit": "V"},
    "voltage_l3_l1": {"addr": 0x183A, "scale": 0.1, "unit": "V"},
    
    # Voltage measurements (Line-to-Neutral)  
    "voltage_l1": {"addr": 0x183C, "scale": 0.1, "unit": "V"},
    "voltage_l2": {"addr": 0x183E, "scale": 0.1, "unit": "V"},
    "voltage_l3": {"addr": 0x1840, "scale": 0.1, "unit": "V"},
    
    # Current measurements
    "current_l1": {"addr": 0x836, "scale": 0.001, "unit": "A"},
    "current_l2": {"addr": 0x838, "scale": 0.001, "unit": "A"},
    "current_l3": {"addr": 0x83A, "scale": 0.001, "unit": "A"},
    "current_neutral": {"addr": 0x83C, "scale": 0.001, "unit": "A"},
    
    # Power measurements (Active)
    "power_l1": {"addr": 0x84A, "scale": 0.001, "unit": "kW"},
    "power_l2": {"addr": 0x84C, "scale": 0.001, "unit": "kW"},
    "power_l3": {"addr": 0x84E, "scale": 0.001, "unit": "kW"},
    "power_total": {"addr": 0x850, "scale": 0.001, "unit": "kW"},
    
    # Power measurements (Reactive)
    "reactive_power_l1": {"addr": 0x852, "scale": 0.001, "unit": "kVAr"},
    "reactive_power_l2": {"addr": 0x854, "scale": 0.001, "unit": "kVAr"},
    "reactive_power_l3": {"addr": 0x856, "scale": 0.001, "unit": "kVAr"},
    "reactive_power_total": {"addr": 0x858, "scale": 0.001, "unit": "kVAr"},
    
    # Power factor
    "power_factor_l1": {"addr": 0x85A, "scale": 0.001, "unit": ""},
    "power_factor_l2": {"addr": 0x85C, "scale": 0.001, "unit": ""},
    "power_factor_l3": {"addr": 0x85E, "scale": 0.001, "unit": ""},
    "power_factor_total": {"addr": 0x860, "scale": 0.001, "unit": ""},
    
    # Energy measurements
    "energy_import_total": {"addr": 0x862, "scale": 0.01, "unit": "kWh"},
    "energy_export_total": {"addr": 0x864, "scale": 0.01, "unit": "kWh"},
    
    # System parameters
    "frequency": {"addr": 0x866, "scale": 0.01, "unit": "Hz"},
}

# Entity mapping types
ENTITY_MAPPING_TYPES = [
    "voltage_l1",
    "voltage_l2", 
    "voltage_l3",
    "current_l1",
    "current_l2",
    "current_l3",
    "power_l1",
    "power_l2",
    "power_l3",
    "power_total",
    "reactive_power_total",
    "power_factor_total",
    "energy_import_total",
    "energy_export_total",
    "frequency",
]

# Required entity mappings for basic functionality
REQUIRED_ENTITIES = [
    "power_total",
    "voltage_l1",
    "frequency",
]

# Default values for unmapped entities (realistic European grid values)
DEFAULT_VALUES = {
    # Voltage measurements (typical European 230V/400V grid)
    "voltage_l1_l2": 400.0,  # V
    "voltage_l2_l3": 400.0,  # V
    "voltage_l3_l1": 400.0,  # V
    "voltage_l1": 230.0,     # V
    "voltage_l2": 230.0,     # V
    "voltage_l3": 230.0,     # V
    
    # Current measurements (calculated from power if not available)
    "current_l1": 0.0,       # A - will be calculated from power/voltage
    "current_l2": 0.0,       # A
    "current_l3": 0.0,       # A
    "current_neutral": 0.0,  # A
    
    # Power measurements
    "power_l1": 0.0,         # kW - will be calculated as total/3 phases
    "power_l2": 0.0,         # kW
    "power_l3": 0.0,         # kW
    "power_total": 0.0,      # kW
    
    # Reactive power (assume good power factor)
    "reactive_power_l1": 0.0,    # kVAr
    "reactive_power_l2": 0.0,    # kVAr
    "reactive_power_l3": 0.0,    # kVAr
    "reactive_power_total": 0.0, # kVAr
    
    # Power factor (typical good values)
    "power_factor_l1": 0.95,     # unitless
    "power_factor_l2": 0.95,     # unitless
    "power_factor_l3": 0.95,     # unitless
    "power_factor_total": 0.95,  # unitless
    
    # Energy measurements (start at 0)
    "energy_import_total": 0.0,  # kWh
    "energy_export_total": 0.0,  # kWh
    
    # System parameters (typical European grid)
    "frequency": 50.0,           # Hz
}