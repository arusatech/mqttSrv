# ERR_HANDSHAKE_TIMEOUT - Analysis & Fixes

## What the error means

`ngtcp2 error: ERR_HANDSHAKE_TIMEOUT` = the client sent QUIC Initial packets but **never received any response** from the server within the timeout (≈7 seconds).

Client logs show:
- Initial packets sent (pkn=0, 1, 2, 3)
- PTO (Probe Timeout) retransmissions
- No server response → handshake timeout

---

## Root cause: packets not reaching end-to-end

Either:
1. **Client → Server**: Packets not reaching your server
2. **Server → Client**: Server response not reaching the iOS device

---

## Checklist & fixes

### 1. Verify server receives packets

**On the server** (while client tries to connect):

```bash
# Check if server logs show new connection
# You should see: "Accepted new connection from <client_ip>"
```

If the server shows **nothing**, packets are not reaching it.

---

### 2. Network / firewall

| Check | Action |
|-------|--------|
| **DDNS** | IP changed (99.37.36.150 → 99.37.36.177). Ensure `cloudflare-ddns.sh` is running and `mqtt.annadata.cloud` points to current IP. |
| **Port forward** | NAT/Gaming: UDP 1884 → server (annadata). Confirm it’s active. |
| **Router firewall** | Allow inbound UDP 1884. |
| **Server firewall** | `sudo ufw status` or `firewall-cmd` – allow UDP 1884. |
| **Client network** | Some cellular networks block or restrict UDP. Try **Wi‑Fi** instead of cellular. |

---

### 3. Certificate (needed once packets work)

Client has `caFile: nil`. For a **self‑signed** server cert:

- System CA store won’t trust it
- After packets get through, you’d see a **certificate verification** error (different from timeout)

**Fix:** Put your CA or server cert in the app and pass it as `caFile`.

1. **Option A – use server cert as trust anchor**  
   Copy `cert.pem` into the iOS app resources and pass its path as `caFile`.

2. **Option B – use CA that signed the server cert**  
   If you used a CA to sign `cert.pem`, bundle that CA cert and pass its path as `caFile`.

3. **Ensure hostname in cert**  
   Server cert must have `mqtt.annadata.cloud` in Subject Alternative Name (SAN). Generate with:

   ```bash
   openssl req -x509 -newkey rsa:2048 -nodes \
     -keyout key.pem -out cert.pem -days 365 \
     -subj "/CN=mqtt.annadata.cloud" \
     -addext "subjectAltName=DNS:mqtt.annadata.cloud,DNS:localhost,IP:127.0.0.1"
   ```

---

### 4. Server listen address

Server binds to `0.0.0.0:1884` (IPv4 only). If the client connects via **IPv6**, the server won’t see it.

- Cloudflare A record is IPv4 only.
- iOS often prefers IPv6 when available.

To also listen on IPv6, `mqttd` would need to bind to `::` or support dual‑stack. Currently it uses `socket.AF_INET` → IPv4 only, which is fine if the client uses the A record and IPv4.

---

### 5. Client connect options

Current connect:

```
host: "mqtt.annadata.cloud"
port: 1884
caFile: nil
```

For a self‑signed cert, add `caFile` once connectivity works:

```typescript
await MqttQuic.connect({
  host: "mqtt.annadata.cloud",
  port: 1884,
  clientId: "Yak1",
  caFile: "/path/to/mqttquic_ca.pem",  // CA or server cert
  // ...
});
```

Replace `mqttquic_ca.pem` with your CA (or server cert) and the correct path in the app bundle.

---

## Quick diagnostic (from your laptop)

```bash
# 1. Resolve hostname
nslookup mqtt.annadata.cloud

# 2. Check UDP reachability
nc -u -v -w 3 mqtt.annadata.cloud 1884
# Type something, Enter. If it connects, UDP path works.

# 3. Ensure DDNS is up to date
# Compare nslookup result with current home IP (router broadband status)
```

---

## Suggested order of actions

1. Run `cloudflare-ddns.sh` and confirm `mqtt.annadata.cloud` resolves to your **current** public IP.
2. Test from the same network first (phone on same Wi‑Fi as server) to rule out cellular UDP blocking.
3. Confirm server logs when the client tries to connect.
4. If packets reach the server but handshake still fails, add `caFile` and regenerate the cert with the correct SAN.

---

## Server vs client alignment

| Component | Server (mqttd) | Client (capacitor-mqtt-quic) |
|-----------|----------------|------------------------------|
| Transport | QUIC (ngtcp2) | QUIC (ngtcp2) |
| ALPN | (ngtcp2 default) | `mqtt` |
| Port | 1884 UDP | 1884 |
| TLS | cert.pem, key.pem | Verifies via system CA or caFile |

Both use ngtcp2 and ALPN `mqtt`; the main problem is connectivity and certificate trust.
