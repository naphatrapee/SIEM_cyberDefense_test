from ingest import enrich as E


def test_private_and_documentation_ips_are_not_looked_up():
    for ip in ("10.0.1.10", "192.168.1.5", "203.0.113.7", "not-an-ip"):
        assert E._is_public(ip) is False
        assert E.reverse_dns(ip) is None


def test_enrich_adds_geo_rdns_and_tag(monkeypatch):
    monkeypatch.setattr(E, "geo_lookup", lambda ip: {"country": "US"} if ip == "8.8.8.8" else None)
    monkeypatch.setattr(E, "reverse_dns", lambda ip: "dns.google" if ip == "8.8.8.8" else None)
    e = E.enrich({"src_ip": "10.0.1.10", "dst_ip": "8.8.8.8", "tags": ["syslog"]})
    assert e["extra"] == {"dst_geo": {"country": "US"}, "dst_rdns": "dns.google"}
    assert e["tags"] == ["syslog", "enriched"]


def test_enrich_without_public_ips_leaves_event_unchanged(monkeypatch):
    monkeypatch.setattr(E, "geo_lookup", lambda ip: None)
    monkeypatch.setattr(E, "reverse_dns", lambda ip: None)
    e = E.enrich({"src_ip": "10.0.0.1", "tags": ["syslog"]})
    assert "extra" not in e and e["tags"] == ["syslog"]


def test_missing_geoip_db_never_raises(monkeypatch):
    monkeypatch.setattr(E, "_reader", None)
    monkeypatch.setattr(E, "_reader_tried", False)
    monkeypatch.setattr(E, "GEOIP_DB_PATH", "/nonexistent.mmdb")
    E.geo_lookup.cache_clear()
    assert E.geo_lookup("8.8.8.8") is None
