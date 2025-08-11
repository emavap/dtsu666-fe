# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Home Assistant HACS integration that emulates a CHINT DTSU666 smart meter for Huawei Sun2000 inverters. The integration allows Home Assistant to act as a virtual energy meter, using existing HA sensor entities to provide power and energy data to Huawei inverters via Modbus TCP/UDP protocol.

## Architecture

The integration consists of:
- **Modbus Server**: Emulates DTSU666 meter registers using pymodbus
- **Entity Mapping**: Configurable mapping from HA entities to Modbus registers
- **Protocol Handler**: Implements specific register layout expected by Huawei inverters
- **Configuration Flow**: UI-based setup for entity mapping and network settings

## Key Components

### Core Files
- `__init__.py`: Integration setup and coordinator
- `config_flow.py`: Configuration UI and validation
- `const.py`: Constants, register mappings, and default values
- `modbus_server.py`: Modbus TCP/UDP server implementation
- `entity_mapper.py`: Maps HA entities to Modbus registers

### Register Mapping
Based on jsphuebner/dtsu666-Emulator, key registers include:
- Voltage measurements (0x1836-0x1848): Line-to-line and line-to-neutral voltages
- Current measurements (0x836-0x848): Phase currents
- Power measurements (0x84A-0x85C): Active/reactive power per phase
- Energy counters: Import/export energy totals
- System parameters: Frequency, power factor

## Development Commands

```bash
# Setup development environment
python -m pip install -r requirements.txt

# Run Home Assistant with custom component
hass --config .

# Test Modbus communication
python -m pytest tests/
```

## Configuration

The integration requires:
- **Network Settings**: IP address and port for Modbus server
- **Entity Mapping**: Map HA sensor entities to power/energy measurements
- **Slave ID**: Modbus device ID (default: 11)
- **Update Interval**: How often to read HA entities (default: 5 seconds)

## Protocol Details

- **Protocol**: Modbus UDP on configurable port (default: 5020)
- **Byte Order**: Big Endian
- **Data Scaling**: Various scales (.1 for voltage, .001 for current, etc.)
- **Device Identification**: Emulates CHINT DTSU666 device