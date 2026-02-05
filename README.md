# mqttsrv

MQTTD server for AI chatBot

## Installation

```bash
poetry install
```

## Usage

```bash
poetry run python srvStart.py
```

## Accessing the Server

The server runs on two ports:
- **TCP MQTT**: `mqtt://localhost:1883` (standard MQTT over TCP)
- **QUIC MQTT**: `quic://localhost:1884` (MQTT over QUIC/UDP)

### Using curl with TCP MQTT

**Subscribe to a topic:**
```bash
curl --output - mqtt://localhost:1883/sensors/temperature
```

**Publish a message:**
```bash
curl -d "25.5" mqtt://localhost:1883/sensors/temperature
```

**Note:** curl does **not** support MQTT over QUIC. For QUIC transport, you'll need a client library that supports QUIC (e.g., Python's `aioquic` or other QUIC-capable MQTT clients).

### Testing the Server

1. **Terminal 1 - Subscribe:**
   ```bash
   curl --output - mqtt://localhost:1883/sensors/temperature
   ```

2. **Terminal 2 - Publish:**
   ```bash
   curl -d "25.5" mqtt://localhost:1883/sensors/temperature
   ```

3. You should see the message appear in Terminal 1.

**Important:** Make sure both subscribe and publish use the **same topic name**!
