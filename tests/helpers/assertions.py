"""TMF-specific test assertions."""


def assert_tmf_resource(data, expected_type=None):
    """Verify a TMF resource has mandatory fields."""
    assert isinstance(data, dict), f"Expected dict, got {type(data)}"
    assert "id" in data, f"Missing 'id' in response: {list(data.keys())}"
    assert "href" in data, f"Missing 'href' in response: {list(data.keys())}"
    if expected_type:
        assert data.get("@type") == expected_type, (
            f"Expected @type={expected_type}, got {data.get('@type')}"
        )
    return data["id"]


def assert_tmf_list(data, min_count=0, expected_type=None):
    """Verify a TMF list response."""
    assert isinstance(data, list), f"Expected list, got {type(data)}"
    assert len(data) >= min_count, f"Expected at least {min_count} items, got {len(data)}"
    for item in data:
        assert_tmf_resource(item, expected_type)
    return data


def assert_tmf_error(resp, expected_status):
    """Verify a TMF error response."""
    assert resp.status_code == expected_status, (
        f"Expected {expected_status}, got {resp.status_code}"
    )
    data = resp.json()
    assert "code" in data or "reason" in data, f"Not a TMF error: {data}"
    return data


def assert_field_present(data, field_name):
    """Verify a specific field exists and is not None."""
    assert field_name in data, f"Missing field '{field_name}' in {list(data.keys())}"
    assert data[field_name] is not None, f"Field '{field_name}' is None"
    return data[field_name]


def assert_field_value(data, field_name, expected_value):
    """Verify a specific field has an expected value."""
    actual = data.get(field_name)
    assert actual == expected_value, (
        f"Expected {field_name}={expected_value}, got {actual}"
    )


def assert_related_party(data, party_id, role=None):
    """Verify relatedParty array contains a reference to party_id."""
    parties = data.get("relatedParty", [])
    found = [p for p in parties if p.get("id") == party_id]
    assert found, f"Party {party_id} not in relatedParty: {parties}"
    if role:
        assert any(p.get("role") == role for p in found), (
            f"Party {party_id} found but not with role={role}"
        )


def assert_odoo_record_exists(odoo, model, domain, msg=""):
    """Verify at least one Odoo record matches domain."""
    ids = odoo.search(model, domain, limit=1)
    assert ids, f"No {model} record found for {domain}. {msg}"
    return ids[0]


def assert_bridge_synced(odoo, model, tmf_id_field, tmf_id_value, odoo_link_field):
    """Verify a TMF record has a linked Odoo record via bridge."""
    recs = odoo.search_read(model, [(tmf_id_field, "=", tmf_id_value)], [odoo_link_field], limit=1)
    assert recs, f"No {model} with {tmf_id_field}={tmf_id_value}"
    link = recs[0].get(odoo_link_field)
    assert link, f"{model}.{odoo_link_field} is empty for {tmf_id_field}={tmf_id_value}"
    return link
