from ingest.normalizers import normalize_syslog

FW = ("<134>Aug 20 12:44:56 fw01 vendor=demo product=ngfw action=deny src=10.0.1.10 "
      "dst=8.8.8.8 spt=5353 dpt=53 proto=udp msg=DNS blocked policy=Block-DNS")


def test_firewall_syslog_fields():
    e = normalize_syslog(FW, "demoA")
    assert e["source"] == "firewall"
    assert e["action"] == "deny"
    assert e["src_ip"] == "10.0.1.10"
    assert e["dst_port"] == 53
    assert e["raw"] == FW
