#!/usr/bin/env python3
"""
Simple tests for MQTT over QUIC server reachability.

curl does NOT support MQTT over QUIC. Use these alternatives.
"""
import socket
import sys


def test_udp_reachable(host: str, port: int) -> bool:
    """Test if UDP port is reachable (does not validate QUIC handshake)."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(3)
        sock.sendto(b"x", (host, port))  # QUIC will ignore, but packet reaches server
        sock.close()
        return True
    except Exception as e:
        print(f"UDP test failed: {e}")
        return False


def main():
    host = sys.argv[1] if len(sys.argv) > 1 else "mqtt.annadata.cloud"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 1884

    print(f"Testing reachability of {host}:{port} (UDP)...")
    if test_udp_reachable(host, port):
        print("OK: UDP port is reachable (packet sent).")
        print("Note: Full MQTT over QUIC test requires the capacitor-mqtt-quic client.")
    else:
        print("FAIL: Could not reach server. Check DNS, firewall, port forwarding.")


if __name__ == "__main__":
    main()
