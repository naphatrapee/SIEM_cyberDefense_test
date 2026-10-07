"""Enrichment at ingest time: GeoIP (offline .mmdb) + reverse DNS.
Results go into event["extra"] as src_geo/dst_geo/src_rdns/dst_rdns and the tag "enriched".
Never raises and never blocks for long: missing DB -> geo skipped, DNS lookups time out at 1s
and results are cached. Only public (global) IPs are looked up."""
import ipaddress
import logging
import os
import socket
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

log = logging.getLogger(__name__)

GEOIP_DB_PATH = os.getenv("GEOIP_DB_PATH", "/data/geoip/city.mmdb")
RDNS_TIMEOUT = float(os.getenv("RDNS_TIMEOUT", "1.0"))
_executor = ThreadPoolExecutor(max_workers=4)
_reader = None
_reader_tried = False


def _is_public(ip) -> bool:
    try:
        return ipaddress.ip_address(str(ip)).is_global
    except ValueError:
        return False


def _geo_reader():
    global _reader, _reader_tried
    if not _reader_tried:
        _reader_tried = True
        try:
            import geoip2.database
            _reader = geoip2.database.Reader(GEOIP_DB_PATH)
        except Exception as exc:
            log.warning("GeoIP disabled (%s)", exc)
    return _reader


@lru_cache(maxsize=4096)
def geo_lookup(ip: str) -> dict | None:
    reader = _geo_reader()
    if reader is None or not _is_public(ip):
        return None
    try:
        r = reader.city(ip)
        geo = {"country": r.country.iso_code, "city": r.city.name}
        return {k: v for k, v in geo.items() if v} or None
    except Exception:
        return None


@lru_cache(maxsize=4096)
def reverse_dns(ip: str) -> str | None:
    if not _is_public(ip):
        return None
    fut = _executor.submit(socket.gethostbyaddr, ip)
    try:
        return fut.result(timeout=RDNS_TIMEOUT)[0]
    except Exception:
        return None


def enrich(event: dict) -> dict:
    extra = event.get("extra") or {}
    for side in ("src", "dst"):
        ip = event.get(f"{side}_ip")
        if not ip:
            continue
        geo = geo_lookup(str(ip))
        if geo:
            extra[f"{side}_geo"] = geo
        name = reverse_dns(str(ip))
        if name:
            extra[f"{side}_rdns"] = name
    if extra:
        event["extra"] = extra
        event["tags"] = list(event.get("tags") or []) + ["enriched"]
    return event
