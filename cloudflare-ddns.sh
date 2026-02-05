#!/bin/bash
# Cloudflare DDNS - Auto-update mqtt.annadata.cloud A record when your IP changes
# Run via cron every 5-10 min: */5 * * * * /home/annadata/api/mqttSrv/cloudflare-ddns.sh

# --- CONFIG (edit these) ---
ZONE_ID="5f9a2352c26e8ce0d02047459d198145"       # Cloudflare: annadata.cloud → Overview → Zone ID
API_TOKEN="t3Xxw03OSuzXQryePama0MtgwjybnqXGYug7NpuR"   # My Profile → API Tokens → Create (Edit zone DNS template)
RECORD_NAME="mqtt"           # mqtt.annadata.cloud
ZONE_NAME="annadata.cloud"   # Your root domain

# --- SCRIPT ---
# Get router's public IPv4 address (try multiple services)
CURRENT_IP=""
for service in "https://api.ipify.org" "https://ifconfig.me/ip" "https://icanhazip.com" "https://ipinfo.io/ip"; do
  CURRENT_IP=$(curl -s --max-time 5 "$service" 2>/dev/null | grep -oE '^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$')
  if [ -n "$CURRENT_IP" ]; then
    echo "$(date): Router public IPv4: $CURRENT_IP (from $service)"
    break
  fi
done

[ -z "$CURRENT_IP" ] && { echo "$(date): Failed to get router's public IPv4 address"; exit 1; }
# Get record ID and current IP
FULL_NAME="${RECORD_NAME}.${ZONE_NAME}"

LIST_RESP=$(curl -s -X GET "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records?name=$FULL_NAME&type=A" \
  -H "Authorization: Bearer $API_TOKEN")
echo "$(date): List response: $LIST_RESP"
RECORD_ID=$(echo "$LIST_RESP" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
CF_IP=$(echo "$LIST_RESP" | grep -o '"content":"[^"]*"' | head -1 | cut -d'"' -f4)
echo "$(date): Record ID: $RECORD_ID"
echo "$(date): CF IP: $CF_IP"
if [ -z "$RECORD_ID" ]; then
  echo "$(date): Record $FULL_NAME not found. Create it in Cloudflare first."
  exit 1
fi

if [ "$CURRENT_IP" != "$CF_IP" ]; then
  echo "$(date): IP changed from $CF_IP to $CURRENT_IP, updating Cloudflare..."
  UPDATE_RESP=$(curl -s -X PATCH "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records/$RECORD_ID" \
    -H "Authorization: Bearer $API_TOKEN" \
    -H "Content-Type: application/json" \
    --data "{\"type\":\"A\",\"name\":\"$RECORD_NAME\",\"content\":\"$CURRENT_IP\",\"ttl\":60}")
  
  if echo "$UPDATE_RESP" | grep -q '"success":true'; then
    echo "$(date): ✓ Updated $FULL_NAME to $CURRENT_IP"
  else
    echo "$(date): ✗ Update failed: $UPDATE_RESP"
    exit 1
  fi
else
  echo "$(date): No change needed ($CURRENT_IP)"
fi
