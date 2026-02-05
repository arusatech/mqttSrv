#!/usr/bin/env python3
"""
MQTT over QUIC Server - QUIC-Only Mode

Server accepts ONLY MQTT over QUIC connections. Compatible with:
- capacitor-mqtt-quic client (Android/iOS via Capacitor)
- MQTT 3.1.1 and MQTT 5.0
- ngtcp2 (production) or pure-Python QUIC fallback

Requires TLS certificates for QUIC (cert.pem, key.pem).
Client uses mqttquic_ca.pem to verify server certificate.
"""

import faulthandler
import logging
import os
import sys

# Dump traceback on segfault to help locate crash (run: PYTHONFAULTHANDLER=1 python srvStart.py)
faulthandler.enable()

# Prefer ref-code/mqttd (ngtcp2 + $HOME/.local lib64 path resolution)
_base = os.path.dirname(os.path.abspath(__file__))
_ref_mqttd = os.path.join(_base, "ref-code", "mqttd")
if os.path.isdir(_ref_mqttd) and _ref_mqttd not in sys.path:
    sys.path.insert(0, _ref_mqttd)

from mqttd import MQTTApp, MQTTMessage, MQTTClient

# Certificate paths (cloudflared / QUIC TLS)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_CERT = os.path.join(BASE_DIR, "cert.pem")
_DEFAULT_KEY = os.path.join(BASE_DIR, "key.pem")
_LE_CERT = "/etc/letsencrypt/live/mqtt.annadata.cloud/fullchain.pem"
_LE_KEY = "/etc/letsencrypt/live/mqtt.annadata.cloud/privkey.pem"

# Allow overrides; prefer Let's Encrypt if present, else fallback to local cert.pem/key.pem
CERT_FILE = os.environ.get("MQTTD_CERT_FILE") or (_LE_CERT if os.path.exists(_LE_CERT) else _DEFAULT_CERT)
KEY_FILE = os.environ.get("MQTTD_KEY_FILE") or (_LE_KEY if os.path.exists(_LE_KEY) else _DEFAULT_KEY)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Create MQTT app: QUIC-only (no TCP) - matches capacitor-mqtt-quic client
# CRITICAL: Bind to actual IP (192.168.1.250) not 0.0.0.0 for ngtcp2 path validation
app = MQTTApp(
    host="192.168.1.250",  # Must use actual interface IP for ngtcp2 amplification limit
    port=1883,  # Ignored when TCP disabled
    enable_tcp=False,
    enable_quic=True,
    quic_port=1884,
    quic_certfile=CERT_FILE,
    quic_keyfile=KEY_FILE,
)


@app.subscribe("devices/#")
async def on_device_subscribe(topic: str, client: MQTTClient):
    """Handle sensor topic subscriptions."""
    logger.info("[%s] Subscribed to %s", client.client_id, topic)


@app.subscribe("live/device/#")
async def on_live_device_subscribe(topic: str, client: MQTTClient):
    """Handle live/device/<session-id>/... subscriptions."""
    logger.info("[%s] Subscribed to %s", client.client_id, topic)


@app.publish_handler("devices/+/response")
async def on_temperature(message: MQTTMessage, client: MQTTClient):
    """Handle temperature publishes from client."""
    logger.info("Temperature from %s: %s", client.client_id, message.payload_str)

@app.publish_handler("devices/+/request")
async def on_device_request(message: MQTTMessage, client: MQTTClient):
    """Handle device registration request (payload = clientId)."""
    client_id = message.payload_str  # The request is nothing but clientId
    logger.info("Device request from %s: %s", client.client_id, client_id)

    # Respond to that client on their response topic
    await app.publish_to_client(
        client,
        topic=f"devices/{client_id}/response",
        payload=b"OK",
        qos=0,
        retain=False,
    )


# Live path: live/device/<session-id>/message (client publishes here)
# Server acks on: live/device/<session-id>/received (client subscribes to show "received")
@app.publish_handler("live/device/+/message")
async def on_live_device_message(message: MQTTMessage, client: MQTTClient):
    """When server receives a message on live/device/<session-id>/message, ack on live/device/<session-id>/received."""
    parts = message.topic.split("/")
    if len(parts) >= 4:
        session_id = parts[2]  # live/device/<session_id>/message
        await app.publish_to_client(
            client,
            topic=f"live/device/{session_id}/received",
            payload=b"received",
            qos=0,
            retain=False,
        )
    else:
        logger.warning("Invalid live/device topic: %s", message.topic)


if __name__ == "__main__":
    logger.info("Using TLS cert: %s", CERT_FILE)
    logger.info("Using TLS key:  %s", KEY_FILE)
    if not os.path.exists(CERT_FILE) or not os.path.exists(KEY_FILE):
        logger.error(
            "TLS certificates required. Create cert.pem and key.pem (e.g. "
            "openssl req -x509 -newkey rsa:2048 -nodes -keyout key.pem -out cert.pem -days 365)"
        )
        raise SystemExit(1)

    print("Starting MQTT over QUIC server (QUIC-only, no TCP)...")
    print("  Listen: quic://0.0.0.0:1884 (UDP)")
    print("  Client: capacitor-mqtt-quic (host, port=1884)")
    print("  Certs:  cert.pem, key.pem")
    print()
    app.run()
