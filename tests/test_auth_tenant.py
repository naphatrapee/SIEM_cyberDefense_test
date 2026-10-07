import pytest
from app.policy import TenantForbidden, filter_fields, resolve_tenant

VIEWER_A = {"role": "viewer", "tenant": "demoA"}
ADMIN = {"role": "admin", "tenant": None}


def test_viewer_is_locked_to_own_tenant():
    assert resolve_tenant(VIEWER_A, None) == "demoA"
    assert resolve_tenant(VIEWER_A, "demoA") == "demoA"


def test_viewer_cannot_request_other_tenant():
    with pytest.raises(TenantForbidden):
        resolve_tenant(VIEWER_A, "demoB")


def test_viewer_without_tenant_claim_is_rejected():
    with pytest.raises(TenantForbidden):
        resolve_tenant({"role": "viewer"}, None)


def test_admin_can_pick_or_see_all():
    assert resolve_tenant(ADMIN, "demoB") == "demoB"
    assert resolve_tenant(ADMIN, None) is None


def test_field_level_rbac():
    row = {"user_name": "alice", "raw": "<original>", "extra": {"src_geo": {}}, "src_ip": "1.2.3.4"}
    assert set(filter_fields("viewer", row)) == {"user_name", "src_ip"}
    assert filter_fields("admin", row) == row
    assert "raw" not in filter_fields("someunknownrole", row)   # unknown role = strictest
