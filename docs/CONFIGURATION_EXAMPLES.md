# Configuration Examples

## Example 1: Basic Solar Installation

For a basic solar installation with a single power meter:

### Entity Mappings:
- **Power Total**: `sensor.solar_power` (total solar production)
- **Voltage L1**: `sensor.grid_voltage` (grid voltage)
- **Frequency**: `sensor.grid_frequency` (grid frequency)

### Huawei Inverter Settings:
- Meter Type: DTSU666
- Communication: Modbus UDP
- IP Address: `192.168.1.100` (Home Assistant IP)
- Port: `5020`
- Slave ID: `11`

## Example 2: Complete 3-Phase System

For a complete 3-phase installation with detailed monitoring:

### Entity Mappings:
- **Power Total**: `sensor.house_total_power`
- **Power L1**: `sensor.house_power_l1`  
- **Power L2**: `sensor.house_power_l2`
- **Power L3**: `sensor.house_power_l3`
- **Voltage L1**: `sensor.grid_voltage_l1`
- **Voltage L2**: `sensor.grid_voltage_l2` 
- **Voltage L3**: `sensor.grid_voltage_l3`
- **Current L1**: `sensor.grid_current_l1`
- **Current L2**: `sensor.grid_current_l2`
- **Current L3**: `sensor.grid_current_l3`
- **Energy Import**: `sensor.energy_consumed_total`
- **Energy Export**: `sensor.energy_produced_total`
- **Frequency**: `sensor.grid_frequency`

## Example 3: Integration with SMA Energy Meter

If you have an SMA Energy Meter providing MQTT data:

### Entity Mappings:
- **Power Total**: `sensor.sma_em_power_total`
- **Power L1**: `sensor.sma_em_power_l1`
- **Power L2**: `sensor.sma_em_power_l2` 
- **Power L3**: `sensor.sma_em_power_l3`
- **Voltage L1**: `sensor.sma_em_voltage_l1`
- **Voltage L2**: `sensor.sma_em_voltage_l2`
- **Voltage L3**: `sensor.sma_em_voltage_l3`
- **Energy Import**: `sensor.sma_em_energy_import`
- **Energy Export**: `sensor.sma_em_energy_export`
- **Frequency**: `sensor.sma_em_frequency`

## Troubleshooting Common Issues

### Inverter Not Connecting
1. Check firewall settings on Home Assistant host
2. Verify network connectivity: `ping <ha_ip>` from inverter network
3. Ensure port 5020 is not used by another service
4. Check inverter logs for Modbus errors

### Data Not Updating
1. Verify entity states in HA Developer Tools
2. Check integration logs for sensor read errors
3. Ensure entity values are numeric (not "unknown" or "unavailable")
4. Verify unit conversions are appropriate

### Register Scaling Issues  
1. Check that power entities are in Watts (not kW)
2. Verify voltage entities are in Volts
3. Ensure energy entities are in kWh
4. Current entities should be in Amperes