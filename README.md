# Cascade Climate

A Home Assistant custom integration that implements sophisticated two-loop cascade control for heating systems with
separate room and radiator temperature control.

[![GitHub Release](https://img.shields.io/github/release/vrlo/ha-cascade-climate.svg)](https://github.com/vrlo/ha-cascade-climate/releases)
[![License](https://img.shields.io/github/license/vrlo/ha-cascade-climate.svg)](LICENSE)
[![hacs](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

## Features

- **Two-loop cascade control** : Outer PI loop controls room temperature by adjusting radiator setpoint; inner
  hysteresis loop switches pump to maintain radiator temperature
- **PI controller with integral action**: Eliminates steady-state error and prevents slow temperature creep
- **Outdoor temperature compensation**: Proactively adjusts heating based on outdoor conditions
- **Weather forecast integration**: Anticipates temperature changes for better control
- **Radiator energy observer** : Optional Kalman-like fusion compensates for sensor lag by blending measurements with
  pump runtime model
- **Pump protection**: Configurable minimum cycle duration prevents excessive wear
- **Activity monitoring**: Shows heating status with flame icon
- **Full history tracking**: All temperatures and control decisions logged

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add repository URL: `https://github.com/vrlo/ha-cascade-climate`
6. Category: "Integration"
7. Click "Add"
8. Find "Cascade Climate" in the integration list and click "Download"
9. Restart Home Assistant

### Manual Installation

1. Download the latest release from [GitHub](https://github.com/vrlo/ha-cascade-climate/releases)
2. Extract and copy the `custom_components/cascade_climate` directory to your Home Assistant `custom_components`
   directory
3. Restart Home Assistant

## Configuration

### Setup

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for "Cascade Climate"
4. Follow the configuration wizard:

**Required:**

- **Room temperature sensor**: Sensor measuring the room/space temperature
- **Radiator temperature sensor**: Sensor measuring the radiator or supply water temperature
- **Pump switch**: Switch entity that controls the heating pump

**Optional:**

- **Outdoor temperature sensor**: For temperature compensation
- **Weather forecast entity**: For proactive control adjustments

### Tuning Parameters

After initial setup, click **Configure** on the integration card to adjust parameters:

#### Control Parameters

- **Base radiator temperature** (10-60°C, default: 35°C): Baseline radiator setpoint when room is at target
- **Proportional gain** (0-20, default: 8.0): How aggressively the controller responds to room temperature error (higher
  = more aggressive)
- **Integral gain** (0-5, default: 0.0): Eliminates steady-state offset; start with small values (0.1-0.3) if needed
- **Minimum radiator temperature** (10-50°C, default: 25°C): Lower limit for radiator setpoint
- **Hysteresis** (0.1-5°C, default: 1.0°C): Temperature band around setpoint for pump switching (prevents rapid cycling)
- **Minimum cycle duration** (30-900s, default: 120s): Minimum time between pump state changes (protects pump)

#### Compensation Parameters

- **Outdoor gain** (0-5, default: 0.3): How much outdoor temperature affects radiator setpoint
- **Outdoor baseline** (-20-30°C, default: 10°C): Outdoor temperature below which compensation begins

#### Observer Parameters

- **Observer mode** (sensor/runtime/fusion, default: sensor):
  - **sensor**: Use radiator sensor directly (traditional)
  - **runtime**: Estimate temperature from pump runtime and heating/cooling rates
  - **fusion**: Blend sensor and runtime model (compensates for sensor lag)
- **Heating rate** (0-1°C/s, default: 0.25): Radiator warm-up rate when pump is on
- **Cooling rate** (0-1°C/s, default: 0.05): Radiator cool-down rate when pump is off
- **Fusion weight** (0-1, default: 0.5): Blend factor (1 = trust sensor, 0 = trust model)
- **Pump dead time** (0-60s, default: 5s): Delay after pump activation before heating begins

## How It Works

### Cascade Control Architecture

1. **Outer Loop (Primary)** : Measures room temperature error (target - actual) and calculates the radiator temperature
   setpoint using a PI controller
2. **Inner Loop (Secondary)** : Compares radiator temperature to setpoint and switches pump on/off with hysteresis to
   maintain it
3. **Feedforward Compensation**: Outdoor temperature and forecast adjusts radiator setpoint proactively
4. **Observer** (optional): Estimates true radiator temperature by fusing sensor data with a thermal model

### Control Equations

**Outer loop** (radiator setpoint):

```text
setpoint = base_temp + Kp × room_error + Ki × ∫room_error dt + outdoor_comp + forecast_comp
```

**Inner loop** (pump control with hysteresis):

```text
Turn pump ON if:  radiator_temp ≤ setpoint - hysteresis/2
Turn pump OFF if: radiator_temp ≥ setpoint + hysteresis/2
```

### Entities Created

The integration creates the following entities:

- **Climate entity** ( `climate.<name>` ): Main thermostat control with target temperature, current temperature, and
  HVAC mode (Heat/Off)
- **Radiator setpoint sensor** ( `sensor.<name>_radiator_setpoint` ): Shows the calculated radiator temperature target
  (outer loop output)
- **Radiator temperature sensor** (`sensor.<name>_radiator_temperature`): Shows current radiator temperature

All entities support full history tracking in Home Assistant.

## Use Cases

This integration is ideal for:

- **Hydronic heating systems**: Radiator-based heating with circulation pump
- **Underfloor heating**: Where radiator sensor measures supply water temperature
- **Zone control**: Individual room control in multi-zone systems
- **Heat pump systems**: With buffer tank or thermal mass
- **Systems with sensor lag**: Use observer fusion mode to compensate for slow temperature sensors

## Troubleshooting

### Enable Debug Logging

Add to `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.cascade_climate: debug
```

Debug logs show control evaluation reasons, pump decisions, setpoint calculations, and sensor updates.

### Common Issues

**Room temperature oscillates:**

- Reduce proportional gain
- Increase hysteresis
- Check minimum cycle duration is adequate

**Room temperature has steady offset:**

- Enable integral gain (start with 0.1-0.2)
- Check outdoor compensation settings

**Pump cycles too frequently:**

- Increase hysteresis
- Increase minimum cycle duration
- Consider enabling observer fusion mode

**Slow response to temperature changes:**

- Increase proportional gain
- Enable outdoor compensation
- Use weather forecast integration

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, testing guidelines, and
pull request process.

## License

This project is licensed under the GPL-3.0 License - see the [LICENSE](LICENSE) file for details.

## Support

- Report bugs or request features: [GitHub Issues](https://github.com/vrlo/ha-cascade-climate/issues)
- Check existing issues before creating new ones
- Include Home Assistant version, integration version, configuration, and logs when reporting bugs
