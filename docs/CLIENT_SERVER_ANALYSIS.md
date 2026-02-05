# MQTT over QUIC: Client–Server Analysis

## Overview

This document summarizes the analysis of:
- **Server**: `ref-code/mqttd` (Python MQTT broker)
- **Client**: `ref-code/capacitor-mqtt-quic` (Capacitor plugin for Android/iOS)

## Server (mqttd)

### Architecture
- **app.py**: Main MQTT application, FastAPI-like decorators
- **transport_quic_ngtcp2.py**: QUIC via ngtcp2 (production)
- **transport_quic_pure.py**: Pure-Python QUIC fallback
- **protocol.py / protocol_v5.py**: MQTT 3.1.1 and 5.0

### QUIC Configuration
| Parameter   | Value  | Notes                          |
|------------|--------|--------------------------------|
| `enable_tcp` | False | QUIC-only mode                 |
| `enable_quic` | True | QUIC enabled                   |
| `quic_port`  | 1884  | UDP port (standard MQTT+QUIC) |
| `quic_certfile` | cert.pem | TLS certificate (required) |
| `quic_keyfile`  | key.pem | TLS private key             |

### MQTT Handler Flow
1. QUIC connection → TLS handshake → bidirectional stream
2. MQTT CONNECT → server sends CONNACK
3. MQTT SUBSCRIBE/PUBLISH/etc. processed by same handler as TCP

### Fix Applied
- **Handler signature**: Transport previously passed `(reader, writer, connection)` but `_handle_client` expects `(reader, writer)`. Fixed both `transport_quic_ngtcp2.py` and `transport_quic_pure.py` to pass only `(reader, writer)`.

---

## Client (capacitor-mqtt-quic)

### Architecture
- **MQTTClient.kt** (Android) / **MQTTClient.swift** (iOS): High-level MQTT API
- **NGTCP2Client.kt** / **NGTCP2Client.swift**: QUIC via ngtcp2 JNI
- **QUICStreamReader/Writer**: Stream adapters for MQTT
- **MQTT5Protocol.kt**, **MQTTProtocol.kt**: MQTT 3.1.1 and 5.0

### Connection Flow
1. `quic.connect(host, port)` → QUIC + TLS
2. `quic.openStream()` → bidirectional stream
3. Build CONNECT (MQTT 3.1.1 or 5.0)
4. Write CONNECT, read CONNACK
5. Start message loop (SUBACK, PUBLISH, PINGREQ, etc.)

### Protocol Version
- `ProtocolVersion.AUTO`: Tries MQTT 5.0 first, fallback to 3.1.1
- Server supports both via `protocol_level` detection

### TLS
- Client uses `mqttquic_ca.pem` to verify server certificate
- Server uses `cert.pem` (must be signed by or match CA in client trust store)

---

## Compatibility Matrix

| Feature          | Server (mqttd)     | Client (capacitor) |
|------------------|--------------------|--------------------|
| Transport        | QUIC (ngtcp2/pure) | QUIC (ngtcp2)      |
| MQTT 3.1.1       | Yes                | Yes                |
| MQTT 5.0         | Yes                | Yes                |
| Port             | 1884 (UDP)         | Configurable       |
| TLS 1.3          | Required            | Required           |
| Bidirectional stream | Yes            | Yes                |

---

## srvStart.py Configuration

```python
app = MQTTApp(
    host="0.0.0.0",
    enable_tcp=False,      # QUIC only
    enable_quic=True,
    quic_port=1884,
    quic_certfile="cert.pem",
    quic_keyfile="key.pem",
)
```

### Handlers
- `@app.subscribe("sensors/#")`: Subscriptions to sensor topics
- `@app.publish_handler("sensors/temperature")`: Temperature publishes

### Run
```bash
python srvStart.py
# or: poetry run python srvStart.py
```

### Client Connection (Capacitor)
```typescript
await MqttQuic.connect({
  host: "your-server-ip",
  port: 1884,
  clientId: "my-client",
  username: null,
  password: null,
  cleanSession: true,
  keepalive: 60,
  protocolVersion: "5.0",  // or "3.1.1" or "auto"
});
```

---

## Certificate Setup

1. **Generate server cert** (for development):
   ```bash
   openssl req -x509 -newkey rsa:2048 -nodes \
     -keyout key.pem -out cert.pem -days 365 \
     -subj "/CN=localhost"
   ```

2. **Client trust**: For the Capacitor app, place `cert.pem` (or the CA that signed it) as `mqttquic_ca.pem` in the client assets so it can verify the server.
