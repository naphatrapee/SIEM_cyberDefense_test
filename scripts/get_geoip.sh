#!/bin/bash
# Downloads the free DB-IP "City Lite" database (MMDB format, readable by geoip2).
# Licence: CC BY 4.0 -> attribution "IP Geolocation by DB-IP" (see docs/architecture.md).
# Alternative: put a MaxMind GeoLite2-City.mmdb at data/geoip/city.mmdb yourself.
set -e
cd "$(dirname "$0")/.."
mkdir -p data/geoip
for offset in 0 1; do   # this month's file may not be published yet -> fall back to last month
  ym=$(date -d "$(date +%Y-%m-15) -$offset month" +%Y-%m)
  url="https://download.db-ip.com/free/dbip-city-lite-$ym.mmdb.gz"
  if curl -fsSL "$url" -o data/geoip/city.mmdb.gz; then
    gunzip -f data/geoip/city.mmdb.gz
    echo "GeoIP database installed from $url"
    exit 0
  fi
done
echo "Could not download the GeoIP database. Place a city .mmdb at data/geoip/city.mmdb manually." >&2
exit 1
