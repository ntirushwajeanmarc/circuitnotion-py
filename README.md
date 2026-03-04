# CircuitNotion Python Library

[![PyPI version](https://badge.fury.io/py/circuitnotion.svg)](https://badge.fury.io/py/circuitnotion)
[![Python versions](https://img.shields.io/pypi/pyversions/circuitnotion.svg)](https://pypi.org/project/circuitnotion/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Python library for connecting Raspberry Pi to the CircuitNotion IoT platform. Control devices, read sensors, and build smart home automation with ease.

## Features

- 🔌 **WebSocket Connection**: Real-time bidirectional communication with CircuitNotion Gate
- 🚀 **Minimal setup**: `begin(api_key, microcontroller_name)` — host defaults to `iot.circuitnotion.com`
- 📊 **Sensor Support**: Temperature, humidity, motion, light, and custom sensors
- 🎛️ **Device Control**: Map GPIO pins, receive on/off and optional `data` (e.g. servo angle 0–180)
- 📧 **Email notifications**: `send_notification(template, **variables)` and `SendNotification()` for alerts
- 🔄 **Auto-reconnect**: Automatic reconnection on connection loss
- 📡 **Real-time Updates**: Receive device control commands instantly
- 🔧 **Easy Integration**: Simple API for quick setup

## Installation

### Basic Installation
```bash
pip install circuitnotion
```

### With GPIO Support
```bash
pip install circuitnotion[gpio]
```

### With Sensor Support (Adafruit sensors)
```bash
pip install circuitnotion[sensors]
```

### Full Installation
```bash
pip install circuitnotion[gpio,sensors]
```

## Quick Start

**Minimal setup** — only your API key and device name; host defaults to `iot.circuitnotion.com`:

```python
import asyncio
from circuitnotion import CN, SensorValue

# Initialize (default host/port/path: iot.circuitnotion.com, 443, /api/ws)
CN.begin("your-api-key-here", "RaspberryPi-01")

# Map a device (relay on GPIO 17)
CN.map_digital_device("GT-001", 17, "Living Room Light")

# Add a temperature sensor
def read_temp():
    # Your sensor reading code here
    return SensorValue(25.5, "°C")

CN.add_temperature_sensor("TEMP-001", "Living Room", 5.0, read_temp)

# Run
asyncio.run(CN.run())
```

**Custom server** — use the full form of `begin()`:

```python
CN.begin("your-server.com", 443, "/api/ws", "your-api-key", "RaspberryPi-01")
```

## Examples

In-repo examples: `examples/dht22_example.py`, `examples/ds18b20_example.py`, `examples/motion_example.py`, `examples/servo_example.py`, `examples/notification_example.py`.

### DHT22 Temperature & Humidity Sensor
```python
import asyncio
import board
import adafruit_dht
from circuitnotion import CN, SensorValue

dht_device = adafruit_dht.DHT22(board.D4, use_pulseio=False)

def read_temperature():
    try:
        temp = dht_device.temperature
        return SensorValue(temp, "°C")
    except RuntimeError:
        return SensorValue(0.0, "°C")

def read_humidity():
    try:
        humidity = dht_device.humidity
        return SensorValue(humidity, "%")
    except RuntimeError:
        return SensorValue(0.0, "%")

async def main():
    CN.begin("your-api-key", "Kitchen-Pi")  # or full: CN.begin("server.com", 443, "/api/ws", "api-key", "Kitchen-Pi")
    
    # Add sensors (read every 5 seconds)
    CN.add_temperature_sensor("DHT22-T", "Kitchen", 5.0, read_temperature)
    CN.add_humidity_sensor("DHT22-H", "Kitchen", 5.0, read_humidity)
    
    # Map relay
    CN.map_digital_device("LIGHT-001", 17, "Kitchen Light")
    
    await CN.run()

asyncio.run(main())
```

### DS18B20 Temperature Sensor (1-Wire)
```python
import asyncio
import glob
from circuitnotion import CN, SensorValue

# Find DS18B20 sensor
device_file = glob.glob('/sys/bus/w1/devices/28*/w1_slave')[0]

def read_temperature():
    with open(device_file, 'r') as f:
        lines = f.readlines()
        temp_pos = lines[1].find('t=')
        temp_c = float(lines[1][temp_pos+2:]) / 1000.0
    return SensorValue(temp_c, "°C")

async def main():
    CN.begin("your-api-key", "Garage-Pi")
    CN.add_temperature_sensor("DS18B20", "Garage", 10.0, read_temperature)
    await CN.run()

asyncio.run(main())
```

### PIR Motion Sensor
```python
import asyncio
import RPi.GPIO as GPIO
from circuitnotion import CN, SensorValue

PIR_PIN = 23
motion_detected = False

def pir_callback(channel):
    global motion_detected
    motion_detected = True

def read_motion():
    global motion_detected
    value = 1.0 if motion_detected else 0.0
    motion_detected = False
    return SensorValue(value, "boolean")

async def main():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(PIR_PIN, GPIO.IN)
    GPIO.add_event_detect(PIR_PIN, GPIO.RISING, callback=pir_callback)
    
    CN.begin("your-api-key", "Entrance-Pi")
    CN.add_motion_sensor("PIR-001", "Front Door", 2.0, read_motion)
    
    try:
        await CN.run()
    finally:
        GPIO.cleanup()

asyncio.run(main())
```

### Servo control (device_control with `data["angle"]`)

When the server sends a device_control for a servo, the payload includes `data` with `angle` (0–180). Use `on_device_control` to receive it and drive your servo:

```python
import asyncio
from circuitnotion import CN

# Optional: use a servo library, e.g. gpiozero or RPi.GPIO + PWM
# from gpiozero import Servo
# servo = Servo(17)

def on_device_control(device_serial: str, state: str, data: dict):
    """Handle on/off and servo angle from CircuitNotion."""
    if data and "angle" in data:
        angle = int(data["angle"])  # 0–180
        # servo.value = (angle / 180.0) * 2 - 1   # gpiozero: -1..1
        # or: my_servo.write(angle)               # other libraries
        print(f"Servo {device_serial} -> angle {angle}°")
    else:
        print(f"Device {device_serial} -> {state}")

async def main():
    CN.begin("your-api-key", "Smart-Blinds-Pi")
    CN.on_device_control(on_device_control)
    # No map_digital_device for servo — drive it in the callback from data["angle"]
    await CN.run()

asyncio.run(main())
```

### Email notifications (threshold alert)

Send an email when a sensor exceeds a threshold using `send_notification`. Uses the host and API key from `begin()`:

```python
import asyncio
from circuitnotion import CN, SensorValue

THRESHOLD_TEMP = 30.0

def read_temperature():
    # Your sensor code here
    return SensorValue(25.5, "°C")

def on_connection(connected: bool):
    if connected:
        print("Connected to CircuitNotion")

async def main():
    CN.begin("your-api-key", "Living-Room-Pi")
    CN.on_connection(on_connection)
    
    # Add temperature sensor (e.g. read every 10 seconds)
    def read_and_maybe_alert():
        value = read_temperature()
        if value.value > THRESHOLD_TEMP:
            CN.send_notification(
                "threshold_alert",
                DeviceName="Living Room",
                SensorType="temperature",
                Value=f"{value.value:.1f}",
                Unit="°C",
                Threshold=str(THRESHOLD_TEMP),
                Message="Temperature is above the safe threshold.",
            )
        return value
    
    CN.add_temperature_sensor("TEMP-001", "Living Room", 10.0, read_and_maybe_alert)
    await CN.run()

asyncio.run(main())
```

Standalone `SendNotification` (when you don’t have a client instance):

```python
from circuitnotion import SendNotification

ok = SendNotification(
    "iot.circuitnotion.com",
    "your-api-key",
    "threshold_alert",
    DeviceName="Living Room",
    SensorType="temperature",
    Value="35",
    Unit="°C",
    Threshold="30",
    Message="Temperature above safe limit.",
)
```

## API Reference

### Initialization

**Minimal (recommended)** — uses default host `iot.circuitnotion.com`, port 443, path `/api/ws`:
```python
CN.begin(api_key, microcontroller_name)
```

**Full** — for a custom server:
```python
CN.begin(host, port, path, api_key, microcontroller_name, use_ssl=True)
```

### Device Mapping
```python
# Digital device (relay, LED, etc.)
CN.map_digital_device(device_serial, pin, device_name, inverted=False)

# Analog/PWM device
CN.map_analog_device(device_serial, pin, device_name)
```

### Sensors
```python
# Add sensors
CN.add_temperature_sensor(device_serial, location, interval, callback)
CN.add_humidity_sensor(device_serial, location, interval, callback)
CN.add_light_sensor(device_serial, location, interval, callback)
CN.add_motion_sensor(device_serial, location, interval, callback)
CN.add_sensor(sensor_type, device_serial, location, interval, callback)

# Manage sensors
CN.enable_sensor(sensor_type, device_serial)
CN.disable_sensor(sensor_type, device_serial)
CN.remove_all_sensors()
```

### Email notifications
```python
# Using the client (uses stored host and API key)
CN.send_notification("threshold_alert",
    DeviceName="Living Room", SensorType="temperature",
    Value="35", Unit="°C", Threshold="30", Message="Above threshold.")

# Standalone function (pass host and API key)
from circuitnotion import SendNotification
SendNotification("iot.circuitnotion.com", "your-api-key", "threshold_alert",
    DeviceName="Living Room", SensorType="temperature", Value="35", Unit="°C", Threshold="30", Message="Above threshold.")
```
Templates: `threshold_alert`, `device_alert`, `custom`.

### Callbacks
```python
# Device control callback (device_serial, state, data — data has e.g. "angle" for servos 0-180)
def on_device_control(device_serial: str, state: str, data: dict):
    print(f"Device {device_serial} -> {state} data={data}")
    if "angle" in data:
        # servo: data["angle"] 0-180
        pass

CN.on_device_control(on_device_control)

# Connection callback
def on_connection(connected: bool):
    print(f"Connected: {connected}")

CN.on_connection(on_connection)

# Custom logging
def on_log(message: str):
    print(f"LOG: {message}")

CN.on_log(on_log)
```

### SensorValue
```python
from circuitnotion import SensorValue

# Simple value
value = SensorValue(25.5, "°C")

# With metadata
value = SensorValue(25.5, "°C", metadata={"location": "outdoor"})
```

## Hardware Setup

### Enable 1-Wire (for DS18B20)
```bash
# Edit /boot/config.txt
sudo nano /boot/config.txt

# Add this line
dtoverlay=w1-gpio

# Reboot
sudo reboot
```

### GPIO Pin Reference (BCM numbering)
- GPIO17 (Pin 11) - Common for relays
- GPIO27 (Pin 13)
- GPIO22 (Pin 15)
- GPIO4 (Pin 7) - Common for DHT sensors
- GPIO23 (Pin 16) - Common for PIR sensors

## Requirements

- Python 3.7+
- Raspberry Pi (any model with GPIO)
- CircuitNotion account and API key

## Supported Sensors

- DHT11/DHT22 (Temperature & Humidity)
- DS18B20 (1-Wire Temperature)
- PIR Motion Sensors
- Photoresistors (Light sensors)
- Any sensor with Python library support

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- 📧 Email: support@circuitnotion.com
- 🐛 Issues: [GitHub Issues](https://github.com/yourusername/circuitnotion-py/issues)
- 📖 Docs: [Documentation](https://github.com/yourusername/circuitnotion-py#readme)

## Changelog

### 1.3.0
- **Minimal `begin(api_key, microcontroller_name)`** — no need to pass host/port/path; defaults to `iot.circuitnotion.com`, 443, `/api/ws`.
- **`send_notification(template, **variables)`** — instance method to send email alerts using stored host and API key.
- **`SendNotification(host, api_key, template, ...)`** — standalone function for email notifications (exported from the package).
- **Device control** — callback now receives `(device_serial, state, data)`; `data` can contain `angle` (0–180) for servos, `volume`, `muted` for speakers. `control_local_device(serial, state, data=None)` accepts optional `data`.
- **Connection helpers** — `disconnect()`, `is_connected()`, `get_status()`, `get_status_string()`, `get_uptime()`, `print_diagnostics()`.

### 1.2.0
- Extended sensor helpers: `add_humidity_sensor`, `add_light_sensor`, `add_motion_sensor`; `enable_sensor`, `disable_sensor`, `remove_all_sensors`.
- `map_analog_device` for PWM/servo mapping.
- `auth_error` handling in WebSocket message handler.

### 1.0.0 (2026-02-08)
- Initial release
- WebSocket connection support
- GPIO device mapping
- Sensor reading and reporting
- Auto-reconnect functionality
- Examples for common sensors

## Author

**Your Name** - [GitHub](https://github.com/yourusername)

---

Made with ❤️ for IoT enthusiasts
```

## `LICENSE`
```
MIT License

Copyright (c) 2026 Your Name

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## `MANIFEST.in`
```
include README.md
include LICENSE
include pyproject.toml
include setup.cfg
recursive-include examples *.py
recursive-exclude * __pycache__
recursive-exclude * *.py[co]
```

## `.gitignore`
```
# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# C extensions
*.so

# Distribution / packaging
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
pip-wheel-metadata/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# PyInstaller
*.manifest
*.spec

# Unit test / coverage reports
htmlcov/
.tox/
.nox/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
*.py,cover
.hypothesis/
.pytest_cache/

# Virtual environments
venv/
env/
ENV/
env.bak/
venv.bak/
.venv/

# IDEs
.idea/
.vscode/
*.swp
*.swo
*~
.DS_Store

# Project specific
*.log
.env