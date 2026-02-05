# Hardcoding MQTT to Use ngtcp2/QUIC in curl

## Answer: Yes, MQTT CAN be hardcoded to use ngtcp2/QUIC

It's technically feasible, but requires modifying curl's source code. Here's how:

## How curl Determines Transport

curl uses `conn->transport_wanted` to determine which transport layer to use:

```c
// From lib/urldata.h
uint8_t transport_wanted; /* one of the TRNSPRT_* defines */
```

**Transport types:**
- `TRNSPRT_TCP` (default for most protocols)
- `TRNSPRT_QUIC` (for HTTP/3)
- `TRNSPRT_UDP` (for TFTP)
- `TRNSPRT_UNIX` (for Unix sockets)

**Connection filter providers** (`lib/cf-ip-happy.c:70-81`):
```c
struct transport_provider transport_providers[] = {
  { TRNSPRT_TCP, Curl_cf_tcp_create },
#if !defined(CURL_DISABLE_HTTP) && defined(USE_HTTP3)
  { TRNSPRT_QUIC, Curl_cf_quic_create },  // ← This creates ngtcp2 connection
#endif
  { TRNSPRT_UDP, Curl_cf_udp_create },
  // ...
};
```

## Current MQTT Implementation

**MQTT currently:**
1. Uses default transport (TCP) - see `lib/url.c:1374`
2. Has `ZERO_NULL` for `connect_it` - uses default connection setup
3. No QUIC transport setup

**MQTT Protocol Structure** (`lib/mqtt.c:982-1000`):
```c
static const struct Curl_protocol Curl_protocol_mqtt = {
  mqtt_setup_conn,                    /* setup_connection */
  mqtt_do,                            /* do_it */
  mqtt_done,                          /* done */
  ZERO_NULL,                          /* do_more */
  ZERO_NULL,                          /* connect_it */  ← No custom connection
  ZERO_NULL,                          /* connecting */
  // ...
};
```

## Solution: Hardcode MQTT to QUIC

### Option 1: Set `transport_wanted` in `mqtt_setup_conn()` (Simplest)

**Modify `lib/mqtt.c`:**

```c
static CURLcode mqtt_setup_conn(struct Curl_easy *data,
                                struct connectdata *conn)
{
  /* setup MQTT specific meta data at easy handle and connection */
  struct mqtt_conn *mqtt;
  struct MQTT *mq;

  // ADD THIS: Force QUIC transport
  conn->transport_wanted = TRNSPRT_QUIC;

  mqtt = curlx_calloc(1, sizeof(*mqtt));
  if(!mqtt ||
     Curl_conn_meta_set(conn, CURL_META_MQTT_CONN, mqtt, mqtt_conn_dtor))
    return CURLE_OUT_OF_MEMORY;

  mq = curlx_calloc(1, sizeof(struct MQTT));
  if(!mq)
    return CURLE_OUT_OF_MEMORY;
  curlx_dyn_init(&mq->recvbuf, DYN_MQTT_RECV);
  curlx_dyn_init(&mq->sendbuf, DYN_MQTT_SEND);
  if(Curl_meta_set(data, CURL_META_MQTT_EASY, mq, mqtt_easy_dtor))
    return CURLE_OUT_OF_MEMORY;
  return CURLE_OK;
}
```

**Add to includes:**
```c
#include "urldata.h"  // For TRNSPRT_QUIC
```

### Option 2: Add `connect_it` Function (More Control)

**Add new function in `lib/mqtt.c`:**

```c
static CURLcode mqtt_connect_it(struct Curl_easy *data, bool *done)
{
  struct connectdata *conn = data->conn;
  CURLcode result;

  // Force QUIC transport
  conn->transport_wanted = TRNSPRT_QUIC;

  // Use default connection setup (which will use QUIC now)
  result = Curl_conn_connect(data, FIRSTSOCKET, FALSE, done);
  if(result)
    connclose(conn, "Failed QUIC connection");
  return result;
}
```

**Update protocol structure:**
```c
static const struct Curl_protocol Curl_protocol_mqtt = {
  mqtt_setup_conn,                    /* setup_connection */
  mqtt_do,                            /* do_it */
  mqtt_done,                          /* done */
  ZERO_NULL,                          /* do_more */
  mqtt_connect_it,                    /* connect_it */  ← Changed from ZERO_NULL
  ZERO_NULL,                          /* connecting */
  // ...
};
```

### Option 3: Create New Scheme `mqttq://` (Best Practice)

**Add new scheme for MQTT over QUIC:**

**In `lib/mqtt.c`, add:**
```c
// New protocol structure for MQTT over QUIC
static const struct Curl_protocol Curl_protocol_mqttq = {
  mqtt_setup_conn,
  mqtt_do,
  mqtt_done,
  ZERO_NULL,
  mqtt_connect_it,  // Uses QUIC
  ZERO_NULL,
  // ...
};

// New scheme
const struct Curl_scheme Curl_scheme_mqttq = {
  "mqttq",                            /* scheme */
  &Curl_protocol_mqttq,
  CURLPROTO_MQTT,                     /* protocol */
  CURLPROTO_MQTT,                     /* family */
  PROTOPT_NONE,                       /* flags */
  1884,                               /* defport - QUIC port */
};
```

**Register in `lib/url.c` scheme table** (add `&Curl_scheme_mqttq`)

## How It Works

1. **Transport Selection** (`lib/connect.c:583`):
   ```c
   result = cf_setup_create(&cf, data, conn->transport_wanted, ssl_mode);
   ```

2. **QUIC Connection Creation** (`lib/cf-ip-happy.c:83-89`):
   ```c
   static cf_ip_connect_create *get_cf_create(uint8_t transport)
   {
     // Finds TRNSPRT_QUIC → returns Curl_cf_quic_create
   }
   ```

3. **ngtcp2 Setup** (`lib/vquic/vquic.c:693-712`):
   ```c
   CURLcode Curl_cf_quic_create(...)
   {
   #if defined(USE_NGTCP2) && defined(USE_NGHTTP3)
     return Curl_cf_ngtcp2_create(pcf, data, conn, ai);  // ← Creates ngtcp2
   #endif
   }
   ```

## Required Build Configuration

For QUIC support, curl must be built with:
- `USE_NGTCP2=1` (ngtcp2 library)
- `USE_NGHTTP3=1` (nghttp3 library)
- OpenSSL with QUIC support OR quictls

**Build flags:**
```bash
./configure --with-ngtcp2 --with-nghttp3
```

## Challenges & Considerations

### 1. **MQTT Protocol over QUIC**
   - MQTT was designed for TCP
   - QUIC is stream-based, MQTT is message-based
   - May need protocol adaptation layer

### 2. **TLS Requirements**
   - QUIC requires TLS (unlike plain TCP MQTT)
   - Need certificate handling
   - May need to modify TLS setup for MQTT

### 3. **Port Conflicts**
   - Standard MQTT: 1883 (TCP)
   - MQTTS: 8883 (TLS/TCP)
   - QUIC MQTT: 1884 (UDP/QUIC) - your server uses this

### 4. **Testing**
   - Need MQTT server that supports QUIC (like yours!)
   - Test connection establishment
   - Test message publish/subscribe
   - Test error handling

## Example Usage After Modification

```bash
# After hardcoding MQTT to QUIC:
curl --output - mqtt://localhost:1884/sensors/temperature

# Or with new scheme:
curl --output - mqttq://localhost:1884/sensors/temperature
```

## Verification Steps

1. **Check transport selection:**
   ```c
   // Add debug in mqtt_setup_conn:
   infof(data, "MQTT using transport: %d", conn->transport_wanted);
   ```

2. **Verify connection filter:**
   - Connection should use `Curl_cf_ngtcp2_create()`
   - Not `Curl_cf_tcp_create()`

3. **Test connection:**
   - Should connect via UDP (QUIC) not TCP
   - Use `netstat` or `ss` to verify UDP connection on port 1884

## Summary

**Yes, MQTT CAN be hardcoded to ngtcp2/QUIC** by:

1. ✅ Setting `conn->transport_wanted = TRNSPRT_QUIC` in MQTT setup
2. ✅ Ensuring curl is built with `--with-ngtcp2 --with-nghttp3`
3. ✅ Handling TLS requirements (QUIC requires TLS)
4. ✅ Testing with a QUIC-capable MQTT server

**Recommended approach:** Option 3 (new `mqttq://` scheme) to maintain backward compatibility with existing `mqtt://` (TCP) usage.
