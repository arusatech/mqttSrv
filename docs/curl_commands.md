# curl MQTT client commands

**Important:** curl uses **TCP** MQTT only. Use **port 1883**, not 1884.
- **1883** = TCP MQTT (curl works here)
- **1884** = QUIC/UDP (curl does **not** support this)

Replace `192.168.1.250` with your server IP when running from a remote machine. Use `localhost` when on the same host.

---

## Subscribe (receive messages)

```bash
# Local
curl --output - mqtt://localhost:1883/sensors/temperature

# Remote
curl --output - mqtt://192.168.1.250:1883/sensors/temperature
```

Subscribe to a wildcard topic:

```bash
curl --output - mqtt://localhost:1883/sensors/#
```

---

## Publish (send message)

```bash
# Local
curl -d "25.5" mqtt://localhost:1883/sensors/temperature

# Remote
curl -d "25.5" mqtt://192.168.1.250:1883/sensors/temperature
```

Publish with a different payload:

```bash
curl -d "hello" mqtt://192.168.1.250:1883/sensors/temperature
```

---

## Quick test (two terminals)

**Terminal 1 – subscribe:**
```bash
curl --output - mqtt://192.168.1.250:1883/sensors/temperature
```

**Terminal 2 – publish:**
```bash
curl -d "42.0" mqtt://192.168.1.250:1883/sensors/temperature
```

You should see the message in Terminal 1.
