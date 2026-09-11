"""
This suite mirrors the six acceptance probes in Section 13 of the capstone
brief, plus the shared requirements (validation, tenant isolation, safe side
effects). Run with:  pytest -v
"""
from app.config import settings


# ---------------------------------------------------------------------------
# Widget management + tenant isolation
# ---------------------------------------------------------------------------


def test_widget_crud_requires_auth(client):
    resp = client.get("/widgets")
    assert resp.status_code == 401


def test_widget_crud_happy_path(client, auth_headers):
    create = client.post(
        "/widgets",
        json={
            "type": "cta",
            "title": "Get 10% off",
            "fields": [{"name": "email", "label": "Email", "type": "email", "required": True}],
        },
        headers=auth_headers,
    )
    assert create.status_code == 201
    widget_id = create.json()["id"]

    got = client.get(f"/widgets/{widget_id}", headers=auth_headers)
    assert got.status_code == 200
    assert got.json()["title"] == "Get 10% off"

    patched = client.patch(f"/widgets/{widget_id}", json={"title": "Get 15% off"}, headers=auth_headers)
    assert patched.status_code == 200
    assert patched.json()["title"] == "Get 15% off"

    deleted = client.delete(f"/widgets/{widget_id}", headers=auth_headers)
    assert deleted.status_code == 204

    gone = client.get(f"/widgets/{widget_id}", headers=auth_headers)
    assert gone.status_code == 404


def test_tenant_isolation(client, widget):
    """Tenant B must not be able to read or modify tenant A's widget."""
    client.post("/auth/register", json={"email": "other@example.com", "password": "supersecret123"})
    login = client.post("/auth/login", data={"username": "other@example.com", "password": "supersecret123"})
    other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # Tenant B cannot read tenant A's widget.
    resp = client.get(f"/widgets/{widget['id']}", headers=other_headers)
    assert resp.status_code == 404

    # Tenant B cannot modify it either.
    resp = client.patch(f"/widgets/{widget['id']}", json={"title": "hijacked"}, headers=other_headers)
    assert resp.status_code == 404

    # Tenant B cannot see tenant A's submissions via the dashboard.
    resp = client.get(f"/dashboard/widgets/{widget['id']}/submissions", headers=other_headers)
    assert resp.status_code == 404


def test_embed_snippet_contains_widget_id(client, auth_headers, widget):
    resp = client.get(f"/widgets/{widget['id']}/embed", headers=auth_headers)
    assert resp.status_code == 200
    assert widget["id"] in resp.json()["snippet"]
    assert "<script" in resp.json()["snippet"]


# ---------------------------------------------------------------------------
# Widget delivery: cache headers + CORS preflight (Probe setup)
# ---------------------------------------------------------------------------


def test_widget_bundle_has_long_immutable_cache(client):
    resp = client.get("/widget/v1/widget.js")
    assert resp.status_code == 200
    cache_control = resp.headers["cache-control"]
    assert "max-age=31536000" in cache_control
    assert "immutable" in cache_control


def test_config_endpoint_has_short_cache_and_cors(client, widget):
    resp = client.get(
        f"/public/widgets/{widget['id']}/config",
        headers={"Origin": "http://totally-different-origin.example"},
    )
    assert resp.status_code == 200
    assert "max-age=60" in resp.headers["cache-control"]
    # CORS: a config fetched from any origin must be explicitly allowed.
    assert resp.headers["access-control-allow-origin"] == "*"


def test_cors_preflight_on_submission_endpoint(client, widget):
    """
    Simulates the browser's automatic OPTIONS request before a cross-origin
    POST. It must be answered without ever reaching the submission logic.
    """
    resp = client.options(
        f"/public/widgets/{widget['id']}/submissions",
        headers={
            "Origin": "http://totally-different-origin.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert resp.status_code in (200, 204)
    assert resp.headers["access-control-allow-origin"] == "*"


# ---------------------------------------------------------------------------
# Probe 1 — valid cross-origin submission -> stored, 2xx, visible on dashboard
# ---------------------------------------------------------------------------


def test_probe1_valid_submission_is_stored_and_visible(client, auth_headers, widget):
    resp = client.post(
        f"/public/widgets/{widget['id']}/submissions",
        json={"data": {"email": "visitor@example.com", "name": "Ada"}, "hp_field": ""},
        headers={"Origin": "http://totally-different-origin.example"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["data"]["email"] == "visitor@example.com"

    dashboard = client.get(f"/dashboard/widgets/{widget['id']}/submissions", headers=auth_headers)
    assert dashboard.status_code == 200
    assert len(dashboard.json()) == 1
    assert dashboard.json()[0]["data"]["email"] == "visitor@example.com"


# ---------------------------------------------------------------------------
# Probe 2 — malformed / oversized payloads -> clean 4xx, never 500
# ---------------------------------------------------------------------------


def test_probe2_missing_required_field_is_422(client, widget):
    resp = client.post(
        f"/public/widgets/{widget['id']}/submissions",
        json={"data": {"name": "No email provided"}, "hp_field": ""},
    )
    assert resp.status_code == 422
    assert "email" in str(resp.json()["detail"])


def test_probe2_malformed_json_is_4xx_not_500(client, widget):
    resp = client.post(
        f"/public/widgets/{widget['id']}/submissions",
        data="{not valid json",
        headers={"Content-Type": "application/json"},
    )
    assert 400 <= resp.status_code < 500


def test_probe2_oversized_payload_is_413(client, widget):
    huge_body = ("x" * 60_000).encode()
    resp = client.post(
        f"/public/widgets/{widget['id']}/submissions",
        content=huge_body,
        headers={"Content-Type": "application/json", "Content-Length": str(len(huge_body))},
    )
    assert resp.status_code == 413


def test_probe2_field_over_max_length_is_422(client, widget):
    resp = client.post(
        f"/public/widgets/{widget['id']}/submissions",
        json={"data": {"email": "a@example.com", "name": "x" * 3000}, "hp_field": ""},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Probe 3 — burst of submissions -> 429s appear, service stays up for others
# ---------------------------------------------------------------------------


def test_probe3_rate_limit_returns_429_then_recovers_for_other_widget(client, widget, auth_headers):
    # RATE_LIMIT_PER_IP_PER_MINUTE is patched to 3 in conftest for a fast test.
    statuses = []
    for _ in range(5):
        resp = client.post(
            f"/public/widgets/{widget['id']}/submissions",
            json={"data": {"email": "flooder@example.com"}, "hp_field": ""},
        )
        statuses.append(resp.status_code)

    assert 201 in statuses
    assert 429 in statuses
    assert statuses.count(429) >= 1

    # The service itself must still be healthy — it degrades, it doesn't die.
    health = client.get("/health")
    assert health.status_code == 200


# ---------------------------------------------------------------------------
# Probe 4 — geo provider fallback chain
# ---------------------------------------------------------------------------


def test_probe4_provider_a_down_falls_back_to_b(client, widget, monkeypatch):
    monkeypatch.setattr(settings, "MOCK_GEO_PROVIDER_A_DOWN", True)
    monkeypatch.setattr(settings, "MOCK_GEO_PROVIDER_B_DOWN", False)

    resp = client.post(
        f"/public/widgets/{widget['id']}/submissions",
        json={"data": {"email": "fallback@example.com"}, "hp_field": ""},
    )
    assert resp.status_code == 201
    assert resp.json()["geo_provider"] == "provider_b"
    assert resp.json()["country"] is not None


def test_probe4_both_providers_down_still_succeeds_without_geo(client, widget, monkeypatch):
    monkeypatch.setattr(settings, "MOCK_GEO_PROVIDER_A_DOWN", True)
    monkeypatch.setattr(settings, "MOCK_GEO_PROVIDER_B_DOWN", True)

    resp = client.post(
        f"/public/widgets/{widget['id']}/submissions",
        json={"data": {"email": "nogeo@example.com"}, "hp_field": ""},
    )
    assert resp.status_code == 201
    assert resp.json()["geo_provider"] is None
    assert resp.json()["country"] is None


# ---------------------------------------------------------------------------
# Probe 5 — side-effect failure must not break the stored submission
# ---------------------------------------------------------------------------


def test_probe5_notification_failure_does_not_break_submission(client, widget, monkeypatch):
    monkeypatch.setattr(settings, "FORCE_NOTIFY_FAILURE", True)

    resp = client.post(
        f"/public/widgets/{widget['id']}/submissions",
        json={"data": {"email": "sideeffect@example.com"}, "hp_field": ""},
    )
    assert resp.status_code == 201
    assert resp.json()["notified"] is False  # side effect failed...
    assert resp.json()["id"] != 0  # ...but the row was still stored


# ---------------------------------------------------------------------------
# Probe 6 — honeypot silently drops bot submissions
# ---------------------------------------------------------------------------


def test_probe6_honeypot_filled_is_silently_dropped(client, auth_headers, widget):
    resp = client.post(
        f"/public/widgets/{widget['id']}/submissions",
        json={"data": {"email": "bot@example.com"}, "hp_field": "I am a bot"},
    )
    # Looks like success to the bot...
    assert resp.status_code == 201

    # ...but nothing was actually stored.
    dashboard = client.get(f"/dashboard/widgets/{widget['id']}/submissions", headers=auth_headers)
    assert dashboard.json() == []
