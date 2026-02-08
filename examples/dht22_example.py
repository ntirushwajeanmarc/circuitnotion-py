#!/usr/bin/env python3
"""
DHT22 Temperature and Humidity Sensor Example
Requires: pip install circuitnotion adafruit-circuitpython-dht adafruit-blinka
"""
import asyncio
import board
import adafruit_dht
from circuitnotion import CN, SensorValue

# DHT22 sensor on GPIO4
dht_device = adafruit_dht.DHT22(board.D4, use_pulseio=False)

def read_temperature():
    """Read temperature from DHT22"""
    try:
        temp_c = dht_device.temperature
        if temp_c is not None:
            return SensorValue(temp_c, "°C")
    except RuntimeError as e:
        print(f"DHT22 read error: {e}")
    return SensorValue(0.0, "°C")

def read_humidity():
    """Read humidity from DHT22"""
    try:
        humidity = dht_device.humidity
        if humidity is not None:
            return SensorValue(humidity, "%")
    except RuntimeError as e:
        print(f"DHT22 read error: {e}")
    return SensorValue(0.0, "%")

def on_device_control(serial: str, state: str):
    """Custom handler for device control"""
    print(f"Device {serial} changed to {state}")

async def main():
    # Initialize CircuitNotion
    CN.begin(
        host="your-server.com",
        port=443,
        path="/ws",
        api_key="your-api-key-here",
        microcontroller_name="RaspberryPi-Kitchen"
    )
    
    # Map relay to control light (GPIO17)
    CN.map_digital_device("GT-001", 17, "Kitchen Light")
    
    # Add DHT22 sensors (read every 5 seconds)
    temp_sensor = CN.add_temperature_sensor("DHT22-TEMP", "Kitchen", 5.0, read_temperature)
    hum_sensor = CN.add_humidity_sensor("DHT22-HUM", "Kitchen", 5.0, read_humidity)
    
    # Optional: Enable change detection (only send if value changes by threshold)
    temp_sensor.set_change_threshold(0.5)  # Send only if temp changes by 0.5°C
    temp_sensor.enable_change_detection(True)
    
    # Set callback for device control
    CN.on_device_control(on_device_control)
    
    try:
        await CN.run()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        dht_device.exit()
        CN.cleanup()

if __name__ == "__main__":
    asyncio.run(main())