"""Per-source normalizers -> common schema. Shared by ingest (syslog) and backend (HTTP)."""
import re
from datetime import datetime, timezone

PRI_RE = re.compile(r"^<(\d+)>")
KV_RE = re.compile(r"(\w+)=(\S+)")


def syslog_severity_to_score(pri: int) -> int:
    """syslog severity 0(emerg)..7(debug) -> schema 0-10 (higher = worse)."""
    return round((7 - (pri % 8)) * 10 / 7)


def normalize_syslog(line: str, tenant: str) -> dict:
    # TODO: parse header timestamp/hostname, detect firewall vs network by content
    m = PRI_RE.match(line)
    pri = int(m.group(1)) if m else 13
    kv = dict(KV_RE.findall(line))
    return {
        "ts": datetime.now(timezone.utc),
        "tenant": tenant,
        "source": "firewall" if "src" in kv else "network",
        "vendor": kv.get("vendor"),
        "product": kv.get("product"),
        "severity": syslog_severity_to_score(pri),
        "action": kv.get("action"),
        "src_ip": kv.get("src"),
        "dst_ip": kv.get("dst"),
        "src_port": int(kv["spt"]) if "spt" in kv else None,
        "dst_port": int(kv["dpt"]) if "dpt" in kv else None,
        "protocol": kv.get("proto"),
        "rule_name": kv.get("policy"),
        "raw": line,
        "tags": ["syslog"],
    }


# TODO: normalize_api, normalize_crowdstrike, normalize_aws, normalize_m365, normalize_ad
NORMALIZERS = {}


def normalize(source: str, payload: dict) -> dict:
    return NORMALIZERS[source](payload)
