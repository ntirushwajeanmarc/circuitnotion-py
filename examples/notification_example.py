#!/usr/bin/env python3
"""
Email notification example: send threshold_alert when temperature exceeds a limit.
Uses CN.send_notification(template, **variables) with stored host and API key.
Requires: pip install circuitnotion
Optional: pip install circuitnotion[sensors] adafruit-circuitpython-dht adafruit-blinka for DHT22.
"""
import asyncio
from circuitnotion import CN, SensorValue

THRESHOLD_TEMP = 30.0

def read_temperature():
    """Return current temperature (replace with your sensor read)."""
    # Example: fake reading; use DHT22 or DS18B20 in production
    return SensorValue(25.5, "°C")

def read_and_maybe_alert():
    """Read temperature; if above threshold, send email via CircuitNotion."""
    value = read_temperature()
    if value.value > THRESHOLD_TEMP:
        sent = CN.send_notification(
            "threshold_alert",
            DeviceName="Living Room",
            SensorType="temperature",
            Value=f"{value.value:.1f}",
            Unit="°C",
            Threshold=str(THRESHOLD_TEMP),
            Message="Temperature is above the safe threshold.",
        )
        if sent:
            print("Alert email sent.")
    return value

async def main():
    CN.begin("your-api-key", "Living-Room-Pi")
    CN.add_temperature_sensor("TEMP-001", "Living Room", 10.0, read_and_maybe_alert)
    try:
        await CN.run()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        CN.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
