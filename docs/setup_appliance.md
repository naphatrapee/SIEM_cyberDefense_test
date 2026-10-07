# Appliance setup (Ubuntu 22.04+, 4 vCPU / 8 GB RAM / 40 GB disk)
1. Install Docker Engine + Compose plugin.
2. `cp .env.example .env` and set every `change_me_*` value (letters/digits only).
3. Optional enrichment database: `make geoip`.
4. `make up` → open `https://localhost` (self-signed certificate: accept the browser warning).
5. Send test data: `make seed`, or `echo -n '<134>...' | nc -u -w1 localhost 514`.

Ports: 80/443 (Caddy), 514 udp+tcp (syslog). PostgreSQL is not published.
Reset everything: `make reset`. The `db/*.sql` + `db/*.sh` scripts only run on the first start of an empty volume.
