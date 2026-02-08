#!/usr/bin/env python3
"""
DS18B20 1-Wire Temperature Sensor Example
Requires: pip install circuitnotion
Enable 1-Wire: Add 'dtoverlay=w1-gpio' to /boot/config.txt
"""
import asyncio
import glob
import time
from circuitnotion import CN, SensorValue

# DS18B20 1-Wire setup
base_dir = '/sys/bus/w1/devices/'
try:
    device_folder = glob.glob(base_dir + '28*')[0]
    device_file = device_folder + '/w1_slave'
except IndexError:
    print("Error: No DS18B20 sensor found!")
    print("Make sure 1-Wire is enabled and sensor is connected")
    exit(1)

def read_temp_raw():
    """Read raw data from DS18B20"""
    with open(device_file, 'r') as f:
        return f.readlines()

def read_temperature():
    """Read temperature from DS18B20"""
    try:
        lines = read_temp_raw()
        # Wait for valid reading
        retries = 0
        while lines[0].strip()[-3:] != 'YES' and retries < 3:
            time.sleep(0.2)
            lines = read_temp_raw()
            retries += 1
            
        if lines[0].strip()[-3:] == 'YES':
            equals_pos = lines[1].find('t=')
            if equals_pos != -1:
                temp_string = lines[1][equals_pos+2:]
                temp_c = float(temp_string) / 1000.0
                return SensorValue(temp_c, "°C")
    except Exception as e:
        print(f"DS18B20 read error: {e}")
    
    return SensorValue(0.0, "°C")

async def main():
    # Initialize CircuitNotion
    CN.begin(
        host="your-server.com",
        port=443,
        path="/ws",
        api_key="your-api-key-here",
        microcontroller_name="RaspberryPi-Garage"
    )
    
    # Add DS18B20 temperature sensor (read every 10 seconds)
    CN.add_temperature_sensor("DS18B20-001", "Garage", 10.0, read_temperature)
    
    # Map a device for control (optional)
    CN.map_digital_device("HEATER-001", 18, "Garage Heater")
    
    try:
        await CN.run()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        CN.cleanup()

if __name__ == "__main__":
    asyncio.run(main())