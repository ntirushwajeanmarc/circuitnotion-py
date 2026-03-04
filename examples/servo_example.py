#!/usr/bin/env python3
"""
Servo control via CircuitNotion device_control.
The server sends device_control with data["angle"] (0-180). Drive your servo in the callback.
Requires: pip install circuitnotion
Optional: pip install gpiozero (or use RPi.GPIO + PWM) for actual servo hardware.
"""
import asyncio
from circuitnotion import CN

# Optional: uncomment and set pin for real hardware
# from gpiozero import Servo
# servo = Servo(17)  # GPIO17

def on_device_control(device_serial: str, state: str, data: dict):
    """Handle on/off and servo angle from CircuitNotion dashboard."""
    data = data or {}
    if "angle" in data:
        angle = int(data["angle"])  # 0-180
        # gpiozero: servo.value = (angle / 180.0) * 2 - 1  # range -1..1
        # other libs: my_servo.write(angle)
        print(f"Servo {device_serial} -> angle {angle}°")
    else:
        print(f"Device {device_serial} -> {state}")

async def main():
    CN.begin("your-api-key", "Smart-Blinds-Pi")
    CN.on_device_control(on_device_control)
    try:
        await CN.run()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        CN.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
