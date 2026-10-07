"""Tenant + field-level RBAC rules. Pure functions (no DB) so they are easy to unit-test.

Tenant: the viewer's tenant always comes from the JWT claim, never from the request.
Fields: each role has a list of fields it must not see (applied to every API response)."""

HIDDEN_FIELDS = {
    "admin": set(),
    "viewer": {"raw", "extra"},   # original message and enrichment internals are admin-only
}


class TenantForbidden(Exception):
    pass


def resolve_tenant(claims: dict, requested: str | None) -> str | None:
    """Return the tenant to filter on. None means 'all tenants' (admin only)."""
    if claims.get("role") == "admin":
        return requested or None
    own = claims.get("tenant")
    if not own:
        raise TenantForbidden("viewer token has no tenant")
    if requested and requested != own:
        raise TenantForbidden("viewer cannot query another tenant")
    return own


def filter_fields(role: str, row: dict) -> dict:
    hidden = HIDDEN_FIELDS.get(role, set(HIDDEN_FIELDS["viewer"]))  # unknown role = strictest
    return {k: v for k, v in row.items() if k not in hidden}
