import asyncio
import json
import logging
import ssl
import time
import urllib.error
import urllib.request
from typing import Callable, Optional, Dict, List, Any
from dataclasses import dataclass
from enum import Enum

import websockets

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    logging.warning("RPi.GPIO not available - GPIO features disabled")


class ConnectionStatus(Enum):
    DISCONNECTED = 0
    CONNECTING = 1
    CONNECTED = 2
    AUTHENTICATED = 3


@dataclass
class SensorValue:
    value: float
    unit: str
    metadata: Optional[Dict] = None


@dataclass
class DeviceMapping:
    serial: str
    pin: int
    is_digital: bool
    name: str = ""
    inverted: bool = False


# Default Gate server – user can override in begin()
DEFAULT_HOST = "iot.circuitnotion.com"
DEFAULT_PORT = 443
DEFAULT_PATH = "/api/ws"


class CircuitNotionSensor:
    def __init__(self, sensor_type: str, device_serial: str, location: str,
                 interval: float, callback: Callable[[], SensorValue]):
        self.type = sensor_type
        self.device_serial = device_serial
        self.location = location
        self.interval = interval
        self.callback = callback
        self.last_reading = 0
        self.threshold = 0.0
        self.last_value = 0.0
        self.change_detection = False
        self.enabled = True

    def should_read(self, current_time: float) -> bool:
        if not self.enabled:
            return False
        return (current_time - self.last_reading) >= self.interval

    def should_send(self, new_value: float) -> bool:
        if not self.change_detection:
            return True
        diff = abs(new_value - self.last_value)
        should_send = diff >= self.threshold
        self.last_value = new_value
        return should_send

    def read(self, current_time: float) -> SensorValue:
        self.last_reading = current_time
        return self.callback()

    def set_change_threshold(self, threshold: float):
        self.threshold = threshold

    def enable_change_detection(self, enabled: bool):
        self.change_detection = enabled

    def set_enabled(self, enabled: bool):
        self.enabled = enabled


class CircuitNotion:
    VERSION = "1.3.0"

    def __init__(self):
        self.host = DEFAULT_HOST
        self.port = DEFAULT_PORT
        self.path = DEFAULT_PATH
        self.api_key = ""
        self.microcontroller_name = ""
        self.use_ssl = True
        
        self.status = ConnectionStatus.DISCONNECTED
        self.is_authenticated = False
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        
        self.device_mappings: List[DeviceMapping] = []
        self.sensors: List[CircuitNotionSensor] = []
        
        self.device_control_callback: Optional[Callable[[str, str, Optional[Dict[str, str]]], None]] = None
        self.log_callback: Optional[Callable[[str], None]] = None
        self.connection_callback: Optional[Callable[[bool], None]] = None
        
        self.total_sensor_readings = 0
        self.total_messages_received = 0
        self.connection_start_time = 0
        
        if GPIO_AVAILABLE:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)

    def begin(
        self,
        host_or_api_key: str,
        port_or_name: Optional[int] = None,
        path: Optional[str] = None,
        api_key: Optional[str] = None,
        microcontroller_name: Optional[str] = None,
        use_ssl: bool = True,
    ):
        """Configure connection. Two forms:
        - Minimal: begin(api_key, microcontroller_name)  → default host/path/port (iot.circuitnotion.com).
        - Full:    begin(host, port, path, api_key, microcontroller_name, use_ssl).
        """
        if (
            port_or_name is not None
            and isinstance(port_or_name, int)
            and path is not None
            and api_key is not None
            and microcontroller_name is not None
        ):
            self.host = host_or_api_key
            self.port = int(port_or_name)
            self.path = path
            self.api_key = api_key
            self.microcontroller_name = microcontroller_name
            self.use_ssl = use_ssl
        else:
            self.api_key = host_or_api_key
            self.microcontroller_name = str(port_or_name) if port_or_name is not None else ""
            self.host = DEFAULT_HOST
            self.port = DEFAULT_PORT
            self.path = DEFAULT_PATH
            self.use_ssl = use_ssl
            if path and "." in path:
                self.host = path
            if api_key is not None and isinstance(api_key, int):
                self.port = api_key
            if microcontroller_name and isinstance(microcontroller_name, str) and microcontroller_name.startswith("/"):
                self.path = microcontroller_name
        self.log(f"CircuitNotion initialized v{self.VERSION}")
        self.log(f"Host: {self.host}:{self.port}")

    def on_device_control(self, callback: Callable[[str, str, Optional[Dict[str, str]]], None]):
        """Set callback for device control messages (device_serial, state, data). data may contain e.g. 'angle' for servos."""
        self.device_control_callback = callback

    def on_log(self, callback: Callable[[str], None]):
        """Set custom logging callback"""
        self.log_callback = callback

    def on_connection(self, callback: Callable[[bool], None]):
        """Set callback for connection status changes"""
        self.connection_callback = callback

    def map_digital_device(self, device_serial: str, pin: int, 
                          device_name: str = "", inverted: bool = False):
        """Map a device serial to a GPIO pin for local control"""
        if not GPIO_AVAILABLE:
            self.log("GPIO not available - mapping stored but inactive")
            return
            
        mapping = DeviceMapping(device_serial, pin, True, device_name, inverted)
        self.device_mappings.append(mapping)
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.HIGH if inverted else GPIO.LOW)
        self.log(f"Mapped digital device: {device_name} ({device_serial}) to pin {pin}")

    def map_analog_device(self, device_serial: str, pin: int, device_name: str = ""):
        """Map an analog/PWM device to a GPIO pin"""
        mapping = DeviceMapping(device_serial, pin, False, device_name)
        self.device_mappings.append(mapping)
        if GPIO_AVAILABLE:
            GPIO.setup(pin, GPIO.OUT)
        self.log(f"Mapped analog device: {device_name} ({device_serial}) to pin {pin}")

    def control_local_device(self, device_serial: str, state: str, data: Optional[Dict[str, str]] = None):
        """Control a locally mapped device. data may contain e.g. 'angle' for servos (0-180)."""
        data = data or {}
        mapping = next((m for m in self.device_mappings if m.serial == device_serial), None)
        if not mapping or not GPIO_AVAILABLE:
            return
        if mapping.is_digital:
            on = state.lower() in ["on", "true", "1"]
            GPIO.output(
                mapping.pin,
                (GPIO.LOW if on else GPIO.HIGH) if mapping.inverted else (GPIO.HIGH if on else GPIO.LOW),
            )
            self.log(f"Set device {device_serial} to {state}")

    def add_sensor(self, sensor_type: str, device_serial: str, location: str,
                   interval: float, callback: Callable[[], SensorValue]) -> CircuitNotionSensor:
        """Add a sensor with custom type"""
        sensor = CircuitNotionSensor(sensor_type, device_serial, location, interval, callback)
        self.sensors.append(sensor)
        self.log(f"Added {sensor_type} sensor for device {device_serial}")
        return sensor

    def add_temperature_sensor(self, device_serial: str, location: str,
                              interval: float, callback: Callable[[], SensorValue]) -> CircuitNotionSensor:
        """Add a temperature sensor"""
        return self.add_sensor("temperature", device_serial, location, interval, callback)
    
    def add_humidity_sensor(self, device_serial: str, location: str,
                           interval: float, callback: Callable[[], SensorValue]) -> CircuitNotionSensor:
        """Add a humidity sensor"""
        return self.add_sensor("humidity", device_serial, location, interval, callback)

    def add_light_sensor(self, device_serial: str, location: str,
                        interval: float, callback: Callable[[], SensorValue]) -> CircuitNotionSensor:
        """Add a light sensor"""
        return self.add_sensor("light", device_serial, location, interval, callback)

    def add_motion_sensor(self, device_serial: str, location: str,
                         interval: float, callback: Callable[[], SensorValue]) -> CircuitNotionSensor:
        """Add a motion sensor"""
        return self.add_sensor("motion", device_serial, location, interval, callback)

    def enable_sensor(self, sensor_type: str, device_serial: str):
        """Enable a specific sensor"""
        for sensor in self.sensors:
            if sensor.type == sensor_type and sensor.device_serial == device_serial:
                sensor.set_enabled(True)
                self.log(f"Enabled sensor: {sensor_type} for device {device_serial}")
                break

    def disable_sensor(self, sensor_type: str, device_serial: str):
        """Disable a specific sensor"""
        for sensor in self.sensors:
            if sensor.type == sensor_type and sensor.device_serial == device_serial:
                sensor.set_enabled(False)
                self.log(f"Disabled sensor: {sensor_type} for device {device_serial}")
                break

    def remove_all_sensors(self):
        """Remove all sensors"""
        self.sensors.clear()
        self.log("Removed all sensors")

    async def connect(self):
        """Connect to CircuitNotion server"""
        self.status = ConnectionStatus.CONNECTING
        self.log("Connecting to CircuitNotion server...")
        
        protocol = "wss" if self.use_ssl else "ws"
        uri = f"{protocol}://{self.host}:{self.port}{self.path}"
        
        try:
            self.ws = await websockets.connect(uri)
            self.status = ConnectionStatus.CONNECTED
            self.connection_start_time = time.time()
            self.log("WebSocket Connected")
            await self._send_auth()
            
            asyncio.create_task(self._message_handler())
            asyncio.create_task(self._sensor_loop())
            asyncio.create_task(self._ping_loop())
            
        except Exception as e:
            self.log(f"Connection failed: {e}")
            self.status = ConnectionStatus.DISCONNECTED
            if self.connection_callback:
                self.connection_callback(False)

    async def disconnect(self):
        """Disconnect from server"""
        if self.ws:
            await self.ws.close()
        self.status = ConnectionStatus.DISCONNECTED
        self.is_authenticated = False
        self.log("Disconnected from CircuitNotion server")
        if self.connection_callback:
            self.connection_callback(False)

    def is_connected(self) -> bool:
        """Check if connected to server"""
        return self.status in [ConnectionStatus.CONNECTED, ConnectionStatus.AUTHENTICATED]

    def get_status(self) -> ConnectionStatus:
        """Get current connection status"""
        return self.status

    def get_status_string(self) -> str:
        """Get connection status as string"""
        return self.status.name.title()

    async def _send_auth(self):
        """Send authentication message"""
        auth_msg = {
            "type": "auth",
            "api_key": self.api_key,
            "microcontroller_name": self.microcontroller_name
        }
        await self.ws.send(json.dumps(auth_msg))
        self.log(f"Sent authentication for: {self.microcontroller_name}")

    async def _message_handler(self):
        """Handle incoming WebSocket messages"""
        try:
            async for message in self.ws:
                self.total_messages_received += 1
                data = json.loads(message)
                msg_type = data.get("type")
                
                if msg_type == "auth_success":
                    self.status = ConnectionStatus.AUTHENTICATED
                    self.is_authenticated = True
                    self.log("Authentication successful")
                    if self.connection_callback:
                        self.connection_callback(True)
                        
                elif msg_type == "auth_error":
                    self.log(f"Authentication failed: {data.get('message', 'Unknown error')}")
                    await self.disconnect()
                        
                elif msg_type == "device_control":
                    device_serial = data.get("device_serial") or data.get("serial_number")
                    state = data.get("state") or data.get("command", "")
                    extra = data.get("data") or {}
                    if isinstance(extra, dict):
                        extra = {k: str(v) for k, v in extra.items()}
                    else:
                        extra = {}
                    self._handle_device_control(device_serial, state, extra)
                    
                elif msg_type == "ping":
                    await self.ws.send(json.dumps({"type": "pong"}))
                    
        except websockets.exceptions.ConnectionClosed:
            self.log("Connection closed")
        except Exception as e:
            self.log(f"Message handler error: {e}")
        finally:
            self.status = ConnectionStatus.DISCONNECTED
            self.is_authenticated = False
            if self.connection_callback:
                self.connection_callback(False)

    def _handle_device_control(self, device_serial: str, state: str, data: Optional[Dict[str, str]] = None):
        """Handle device control command"""
        data = data or {}
        self.control_local_device(device_serial, state, data)
        if self.device_control_callback:
            self.device_control_callback(device_serial, state, data)
        self.log(f"Device control: {device_serial} -> {state}" + (f" data={data}" if data else ""))

    async def _sensor_loop(self):
        """Continuously read and send sensor data"""
        while self.status == ConnectionStatus.AUTHENTICATED:
            current_time = time.time()
            for sensor in self.sensors:
                if sensor.should_read(current_time):
                    try:
                        value = sensor.read(current_time)
                        if sensor.should_send(value.value):
                            await self._send_sensor_reading(sensor, value)
                            self.total_sensor_readings += 1
                    except Exception as e:
                        self.log(f"Error reading sensor {sensor.device_serial}: {e}")
            await asyncio.sleep(0.1)

    async def _send_sensor_reading(self, sensor: CircuitNotionSensor, value: SensorValue):
        """Send sensor reading to server"""
        msg = {
            "type": "sensor_reading",
            "sensor_type": sensor.type,
            "device_serial": sensor.device_serial,
            "location": sensor.location,
            "value": value.value,
            "unit": value.unit,
            "timestamp": int(time.time() * 1000),
            "microcontroller": self.microcontroller_name
        }
        if value.metadata:
            msg["metadata"] = value.metadata
            
        await self.ws.send(json.dumps(msg))
        self.log(f"Sent {sensor.type} reading: {value.value} {value.unit}")

    async def _ping_loop(self):
        """Send periodic ping to keep connection alive"""
        while self.status == ConnectionStatus.AUTHENTICATED:
            await asyncio.sleep(30)
            try:
                await self.ws.send(json.dumps({"type": "ping"}))
            except Exception:
                break

    def log(self, message: str):
        """Log a message"""
        if self.log_callback:
            self.log_callback(message)
        else:
            print(f"[CircuitNotion] {message}")

    def send_notification(
        self,
        template: str,
        subject: Optional[str] = None,
        body: Optional[str] = None,
        **variables: str,
    ) -> bool:
        """Send email notification using stored host and API key.
        Example: cn.send_notification("threshold_alert", DeviceName="Living Room",
            SensorType="temperature", Value="35", Unit="°C", Threshold="30", Message="Above threshold.")
        """
        return SendNotification(
            self.host,
            self.api_key,
            template,
            subject=subject,
            body=body,
            port=self.port,
            use_ssl=self.use_ssl,
            **variables,
        )

    def get_uptime(self) -> float:
        """Get connection uptime in seconds"""
        if self.connection_start_time > 0:
            return time.time() - self.connection_start_time
        return 0

    def print_diagnostics(self):
        """Print diagnostic information"""
        self.log("=== CircuitNotion Diagnostics ===")
        self.log(f"Library Version: {self.VERSION}")
        self.log(f"Status: {self.get_status_string()}")
        self.log(f"Microcontroller: {self.microcontroller_name}")
        self.log(f"Host: {self.host}:{self.port}")
        self.log(f"Sensors: {len(self.sensors)}")
        self.log(f"Device Mappings: {len(self.device_mappings)}")
        self.log(f"Total Sensor Readings: {self.total_sensor_readings}")
        self.log(f"Total Messages Received: {self.total_messages_received}")
        self.log(f"Uptime: {self.get_uptime():.2f}s")

    async def run(self):
        """Main run loop - connect and stay connected"""
        await self.connect()
        try:
            while True:
                if self.status == ConnectionStatus.DISCONNECTED:
                    self.log("Reconnecting in 5 seconds...")
                    await asyncio.sleep(5)
                    await self.connect()
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            self.log("Shutting down...")
        finally:
            await self.disconnect()
            self.cleanup()

    def cleanup(self):
        """Cleanup GPIO resources"""
        if GPIO_AVAILABLE:
            try:
                GPIO.cleanup()
                self.log("GPIO cleanup completed")
            except Exception as e:
                self.log(f"GPIO cleanup error: {e}")


# Global instance
CN = CircuitNotion()


def SendNotification(
    host: str,
    api_key: str,
    template: str,
    subject: Optional[str] = None,
    body: Optional[str] = None,
    port: Optional[int] = None,
    use_ssl: bool = True,
    **variables: str,
) -> bool:
    """
    Send an email notification to the user associated with the API key.
    The server sends the email to the user's registered address using the given template.

    Args:
        host: Gate server host (e.g. "iot.circuitnotion.com").
        api_key: Microcontroller API key (from CircuitNotion dashboard).
        template: One of "threshold_alert", "device_alert", "custom".
        subject: Optional subject (for custom template).
        body: Optional HTML body (for custom template).
        port: Server port (default 443 if use_ssl, else 80).
        use_ssl: Use HTTPS (default True).
        **variables: Template variables, e.g. DeviceName, SensorType, Value, Unit, Threshold, Message for threshold_alert.

    Returns:
        True if the server accepted and sent the email, False otherwise.

    Example (threshold alert):
        SendNotification(
            "iot.circuitnotion.com",
            "your-api-key",
            "threshold_alert",
            DeviceName="Living Room Sensor",
            SensorType="temperature",
            Value="35.2",
            Unit="°C",
            Threshold="30",
            Message="Temperature is above the safe threshold.",
        )
    """
    if port is None:
        port = 443 if use_ssl else 80
    scheme = "https" if use_ssl else "http"
    if (use_ssl and port == 443) or (not use_ssl and port == 80):
        url = f"{scheme}://{host}/api/notify"
    else:
        url = f"{scheme}://{host}:{port}/api/notify"
    payload = {
        "template": template,
        "variables": dict(variables),
    }
    if subject:
        payload["subject"] = subject
    if body:
        payload["body"] = body
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-API-Key": api_key,
        },
        method="POST",
    )
    try:
        ctx = ssl.create_default_context() if use_ssl else None
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            return resp.status == 200 and json.loads(resp.read().decode()).get("sent") is True
    except urllib.error.HTTPError as e:
        logging.warning("SendNotification failed: %s %s", e.code, e.read())
        return False
    except Exception as e:
        logging.warning("SendNotification error: %s", e)
        return False