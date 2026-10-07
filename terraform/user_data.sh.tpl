#!/bin/bash
set -euo pipefail   # no -x: it would write secrets to the cloud-init log
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y git make curl netcat-openbsd
curl -fsSL https://get.docker.com | sh

git clone ${repo_url} /opt/logdemo
cd /opt/logdemo
cat > .env <<ENVEOF
POSTGRES_USER=logadmin
POSTGRES_PASSWORD=${owner_pw}
APP_DB_PASSWORD=${app_pw}
POSTGRES_DB=logdb
JWT_SECRET=${jwt}
ADMIN_PASSWORD=${admin_pw}
VIEWER_PASSWORD=${viewer_pw}
DOMAIN=${domain != "" ? domain : "localhost"}
RETENTION_DAYS=7
ALERT_WEBHOOK_URL=
DEFAULT_TENANT=demoA
GEOIP_DB_PATH=/data/geoip/city.mmdb
RDNS_TIMEOUT=1.0
ENVEOF
chmod 600 .env

%{ if duckdns_token != "" ~}
# Point the DuckDNS name at this VM before Caddy asks Let's Encrypt for a certificate
curl -fsS "https://www.duckdns.org/update?domains=${replace(domain, ".duckdns.org", "")}&token=${duckdns_token}&ip=" || true
%{ endif ~}

make geoip || true   # optional enrichment database; ignore failure
make up
