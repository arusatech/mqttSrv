# MQTT over QUIC Support in curl - Analysis

## Summary

After thorough analysis of the curl reference codebase (`/home/annadata/api/MQTTD/reference/curl`), **curl does NOT support MQTT over QUIC**, even though curl has both:
- MQTT protocol support (`mqtt://` and `mqtts://`)
- QUIC transport support (via ngtcp2/nghttp3 for HTTP/3)

## Key Findings

### 1. MQTT Protocol Implementation (`lib/mqtt.c`)

- **Schemes supported**: Only `mqtt://` (TCP) and `mqtts://` (TLS over TCP)
- **Default ports**: 
  - `mqtt://` → 1883 (TCP)
  - `mqtts://` → 8883 (TLS over TCP)
- **Connection setup**: Uses `mqtt_setup_conn()` which does NOT specify QUIC transport
- **No QUIC references**: Zero mentions of `QUIC`, `ngtcp2`, `nghttp3`, or `TRNSPRT_QUIC` in `lib/mqtt.c`

### 2. QUIC Transport Implementation (`lib/vquic/`)

- **QUIC support exists**: curl has full QUIC support via:
  - `ngtcp2` (primary implementation)
  - `nghttp3` (HTTP/3 layer)
  - `quiche` (alternative implementation)
- **Usage**: QUIC is used **only** for HTTP/3 (`h3://` or `https://` with `--http3` flag)
- **Connection filter**: `Curl_cf_ngtcp2_create()` creates QUIC connection filters
- **Transport type**: Uses `TRNSPRT_QUIC` enum value

### 3. How HTTP/3 Uses QUIC

HTTP/3 determines QUIC transport via:
- ALPN (Application-Layer Protocol Negotiation) negotiation
- When `ALPN_h3` is negotiated, sets `conn->transport_wanted = TRNSPRT_QUIC`
- Then uses `Curl_cf_quic_create()` → `Curl_cf_ngtcp2_create()`

### 4. MQTT vs HTTP/3 Transport Selection

| Protocol | Transport | How Determined |
|----------|-----------|----------------|
| HTTP/3   | QUIC      | ALPN negotiation (`ALPN_h3`) |
| MQTT     | TCP       | Hardcoded (no QUIC option) |
| MQTTS    | TLS/TCP   | Hardcoded (no QUIC option) |

### 5. Code Evidence

**MQTT Scheme Definition** (`lib/mqtt.c:1022-1033`):
```c
const struct Curl_scheme Curl_scheme_mqtt = {
  "mqtt",                             /* scheme */
  &Curl_protocol_mqtt,
  CURLPROTO_MQTT,                     /* protocol */
  CURLPROTO_MQTT,                     /* family */
  PROTOPT_NONE,                       /* flags */
  PORT_MQTT,                          /* defport */
};
```

**MQTT Protocol Structure** (`lib/mqtt.c:982-1000`):
```c
static const struct Curl_protocol Curl_protocol_mqtt = {
  mqtt_setup_conn,                    /* setup_connection */
  mqtt_do,                            /* do_it */
  // ... no QUIC transport setup
};
```

**No QUIC Integration**: 
- `mqtt_setup_conn()` does NOT set `transport_wanted = TRNSPRT_QUIC`
- MQTT does NOT use `Curl_cf_quic_create()` or `Curl_cf_ngtcp2_create()`
- MQTT uses standard TCP socket connections via `Curl_conn_connect()`

## Conclusion

**curl does NOT support MQTT over QUIC** because:

1. ✅ curl has MQTT support (TCP only)
2. ✅ curl has QUIC support (for HTTP/3 only)
3. ❌ MQTT and QUIC are **not integrated** - MQTT is hardcoded to use TCP
4. ❌ No code path exists to route MQTT over QUIC transport
5. ❌ No URL scheme like `mqtt+quic://` or `mqttq://` exists

## Recommendations

To use MQTT over QUIC, you would need:

1. **Use a different client** that supports MQTT over QUIC (e.g., Python with `aioquic` or specialized MQTT libraries)
2. **Modify curl** to add MQTT over QUIC support (significant code changes required)
3. **Use TCP MQTT** with curl (current working solution)

## References

- `lib/mqtt.c` - MQTT protocol implementation
- `lib/mqtt.h` - MQTT header (only defines `mqtt://` and `mqtts://`)
- `lib/vquic/vquic.c` - QUIC transport layer
- `lib/vquic/curl_ngtcp2.c` - ngtcp2 QUIC implementation
- `lib/url.c` - URL scheme handling (no MQTT+QUIC scheme)
