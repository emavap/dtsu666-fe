# DTSU666-FE Emulator for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub release](https://img.shields.io/github/release/marcocamilli/dtsu666-FE.svg)](https://github.com/marcocamilli/dtsu666-FE/releases)

A Home Assistant HACS integration that emulates a CHINT DTSU666 smart meter for Huawei Sun2000 inverters. This allows your Home Assistant installation to act as a virtual energy meter, providing power and energy data to Huawei inverters via Modbus TCP/UDP protocol.

## Features

- **Modbus UDP Server**: Emulates DTSU666 registers using configurable network settings
- **Entity Mapping**: Map existing HA sensor entities to Modbus registers
- **Protocol Compatibility**: Implements the specific register layout expected by Huawei Sun2000 inverters
- **Configuration UI**: Easy setup through Home Assistant's configuration flow
- **Real-time Updates**: Continuously updates Modbus registers with current HA sensor values
- **Diagnostic Sensors**: Exposes actual register values and server status for monitoring
- **Intelligent Defaults**: Provides realistic default values for unmapped entities
- **Failure Simulation**: Stops responding when required entities are unavailable (realistic meter behavior)

## Installation

### Via HACS (Recommended)

1. Add this repository to HACS as a custom repository
2. Search for "DTSU666-FE Emulator" in HACS
3. Install the integration
4. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/dtsu666_emulator` folder to your HA `custom_components` directory
2. Restart Home Assistant

## Configuration

1. Go to Settings → Devices & Services
2. Click "Add Integration" 
3. Search for "DTSU666 Emulator"
4. Configure network settings:
   - **Host**: IP address to bind the server (default: 0.0.0.0)
   - **Port**: Modbus port (default: 5020)
   - **Slave ID**: Modbus device ID (default: 11)
   - **Update Interval**: How often to read HA entities (default: 5 seconds)

5. Map your existing HA sensor entities to the required registers:
   - **Power Total** (required): Total power consumption/production
   - **Voltage L1** (required): Line voltage  
   - **Frequency** (required): Grid frequency
   - Optional: Individual phase currents, powers, reactive power, energy totals

## Supported Registers

The integration emulates these DTSU666 registers:

| Register | Address | Description | Unit | Scale |
|----------|---------|-------------|------|-------|
| Voltage L1-L2 | 0x1836 | Line-to-line voltage | V | 0.1 |
| Voltage L1 | 0x183C | Line-to-neutral voltage | V | 0.1 |
| Current L1 | 0x836 | Phase current | A | 0.001 |
| Power L1 | 0x84A | Active power | kW | 0.001 |
| Power Total | 0x850 | Total active power | kW | 0.001 |
| Reactive Power | 0x858 | Total reactive power | kVAr | 0.001 |
| Power Factor | 0x860 | Power factor | - | 0.001 |
| Energy Import | 0x862 | Imported energy | kWh | 0.01 |
| Energy Export | 0x864 | Exported energy | kWh | 0.01 |
| Frequency | 0x866 | Grid frequency | Hz | 0.01 |

## Huawei Inverter Setup

1. Connect your Huawei Sun2000 inverter to the same network as Home Assistant
2. Configure the inverter's smart meter settings:
   - **Meter Type**: DTSU666
   - **Communication**: Modbus UDP
   - **IP Address**: Home Assistant IP
   - **Port**: 5020 (or your configured port)
   - **Slave ID**: 11 (or your configured slave ID)

## Diagnostic Sensors

The integration automatically creates diagnostic sensors to monitor register values:

### **Register Sensors**
For each register (mapped + defaults), you'll get a sensor showing:
- **Current Value**: The actual value being sent to the inverter  
- **Register Address**: Modbus register address (hex)
- **Scale Factor**: Applied scaling factor
- **Source Entity**: The HA entity providing the data (or "default")
- **Raw Value**: Unscaled integer value in the register

### **Server Status Sensor** 
Shows server status with detailed diagnostics:
- **Status**: `running` / `stopped` / `meter_failed`
- **Network Settings**: host, port, slave ID
- **Configuration**: update interval, mapped entities count
- **Required Entities Status**: Health check of critical entities
- **Meter Failed**: Boolean indicating if meter is simulating failure

## Default Values

When entities are not mapped, the integration uses realistic defaults:
- **Voltages**: 230V (L-N), 400V (L-L) - typical European grid
- **Power Factor**: 0.95 - typical good power factor
- **Frequency**: 50Hz - European grid standard  
- **Power/Current/Energy**: 0.0 - no load

## Meter Failure Simulation

**Critical Behavior**: If any required entity (`power_total`, `voltage_l1`, `frequency`) becomes unavailable or has invalid values, the meter **stops responding** to simulate a real meter failure. This prevents the Huawei inverter from receiving incorrect data.

**Recovery**: Once all required entities are available again, the meter automatically resumes normal operation.

## Troubleshooting

### Connection Issues
- Ensure firewall allows connections on the configured port
- Check that no other service is using the same port
- Verify network connectivity between inverter and HA

### Data Issues  
- Ensure mapped entities have valid numeric values
- Check entity states are not "unknown" or "unavailable"
- Verify entity units match expected register types

### Logs
Enable debug logging for detailed troubleshooting:

```yaml
logger:
  logs:
    custom_components.dtsu666_emulator: debug
    pymodbus: debug
```

## Based On

This integration is inspired by and based on the [dtsu666-Emulator](https://github.com/jsphuebner/dtsu666-Emulator) project by jsphuebner.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.