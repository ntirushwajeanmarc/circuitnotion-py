#!/usr/bin/env python3
"""
PIR Motion Sensor Example
Requires: pip install circuitnotion RPi.GPIO
"""
import asyncio
import RPi.GPIO as GPIO
from circuitnotion import CN, SensorValue

PIR_PIN = 23
motion_detected = False

def pir_callback(channel):
    """GPIO interrupt callback for PIR sensor"""
    global motion_detected
    motion_detected = True
    print("Motion detected!")

def read_motion():
    """Read motion sensor state"""
    global motion_detected
    value = 1.0 if motion_detected else 0.0
    motion_detected = False  # Reset after reading
    return SensorValue(value, "boolean")

def on_device_control(serial: str, state: str):
    """Handle device control from server"""
    print(f"Device {serial} set to {state}")
    if serial == "ALARM-001":
        # Could trigger an alarm, send notification, etc.
        print(f"Alarm is now {state}")

async def main():
    # Setup PIR sensor
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(PIR_PIN, GPIO.IN)
    GPIO.add_event_detect(PIR_PIN, GPIO.RISING, callback=pir_callback)
    
    # Initialize CircuitNotion
    CN.begin(
        host="your-server.com",
        port=443,
        path="/ws",
        api_key="your-api-key-here",
        microcontroller_name="RaspberryPi-Entrance"
    )
    
    # Add motion sensor (check every 2 seconds)
    CN.add_motion_sensor("PIR-001", "Front Door", 2.0, read_motion)
    
    # Map devices for control
    CN.map_digital_device("LIGHT-001", 17, "Entrance Light")
    CN.map_digital_device("ALARM-001", 27, "Alarm System")
    
    # Set callback
    CN.on_device_control(on_device_control)
    
    try:
        await CN.run()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        GPIO.cleanup()
        CN.cleanup()

if __name__ == "__main__":
    asyncio.run(main())