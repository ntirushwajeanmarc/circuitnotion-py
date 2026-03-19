import asyncio
import RPi.GPIO as GPIO
from circuitnotion import CN

BUTTON_PIN = 23
RELAY_PIN = 17
DEVICE_SERIAL = "LIGHT-001"

# Track local physical state so every button press toggles.
physical_state = "off"


def on_device_control(device_serial: str, state: str, data: dict):
    """Apply server-issued state changes to local relay."""
    if device_serial != DEVICE_SERIAL:
        return
    GPIO.output(RELAY_PIN, GPIO.HIGH if state == "on" else GPIO.LOW)
    print(f"Remote control: {device_serial} -> {state}")


def on_button_pressed(channel: int):
    """GPIO callback: toggle local relay and notify Gate immediately."""
    global physical_state
    physical_state = "off" if physical_state == "on" else "on"
    GPIO.output(RELAY_PIN, GPIO.HIGH if physical_state == "on" else GPIO.LOW)
    CN.report_device_state_change_from_callback(
        DEVICE_SERIAL,
        physical_state,
        source="physical_button",
        metadata={"pin": str(BUTTON_PIN)},
    )
    print(f"Physical button: {DEVICE_SERIAL} -> {physical_state}")


async def main():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(RELAY_PIN, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.add_event_detect(BUTTON_PIN, GPIO.FALLING, callback=on_button_pressed, bouncetime=200)

    CN.begin("your-api-key", "RaspberryPi-ButtonNode")
    CN.map_digital_device(DEVICE_SERIAL, RELAY_PIN, "Living Room Light")
    CN.on_device_control(on_device_control)

    try:
        await CN.run()
    finally:
        GPIO.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
