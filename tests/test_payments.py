from datetime import datetime, timedelta, timezone

FUTURE = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()


def _make_booking(client, auth_headers, seeded_test):
    return client.post(
        "/bookings/", json={"test_id": seeded_test["id"], "appointment_time": FUTURE}, headers=auth_headers
    ).json()


def test_payment_success_confirms_booking(client, auth_headers, seeded_test):
    booking = _make_booking(client, auth_headers, seeded_test)
    resp = client.post(
        "/payments/", json={"booking_id": booking["id"], "force_result": "SUCCESS"}, headers=auth_headers
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "SUCCESS"

    booking_after = client.get(f"/bookings/{booking['id']}", headers=auth_headers).json()
    assert booking_after["status"] == "CONFIRMED"


def test_payment_failure_marks_booking_failed(client, auth_headers, seeded_test):
    booking = _make_booking(client, auth_headers, seeded_test)
    resp = client.post(
        "/payments/", json={"booking_id": booking["id"], "force_result": "FAILED"}, headers=auth_headers
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "FAILED"

    booking_after = client.get(f"/bookings/{booking['id']}", headers=auth_headers).json()
    assert booking_after["status"] == "FAILED"


def test_cannot_pay_for_others_booking(client, auth_headers, seeded_test):
    booking = _make_booking(client, auth_headers, seeded_test)
    client.post("/auth/signup", json={"email": "payer2@example.com", "password": "password123"})
    other_token = client.post(
        "/auth/login", json={"email": "payer2@example.com", "password": "password123"}
    ).json()["access_token"]

    resp = client.post(
        "/payments/",
        json={"booking_id": booking["id"], "force_result": "SUCCESS"},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 403


def test_cannot_pay_twice_for_same_booking(client, auth_headers, seeded_test):
    booking = _make_booking(client, auth_headers, seeded_test)
    client.post(
        "/payments/", json={"booking_id": booking["id"], "force_result": "SUCCESS"}, headers=auth_headers
    )
    resp = client.post(
        "/payments/", json={"booking_id": booking["id"], "force_result": "SUCCESS"}, headers=auth_headers
    )
    assert resp.status_code == 409


def test_cannot_pay_for_invalid_booking_id(client, auth_headers):
    resp = client.post(
        "/payments/", json={"booking_id": "does-not-exist", "force_result": "SUCCESS"}, headers=auth_headers
    )
    assert resp.status_code == 404


def test_webhook_confirms_booking(client, auth_headers, seeded_test):
    booking = _make_booking(client, auth_headers, seeded_test)
    resp = client.post(
        "/payments/webhook/",
        json={"event_id": "evt_1", "booking_id": booking["id"], "status": "SUCCESS"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "processed"

    booking_after = client.get(f"/bookings/{booking['id']}", headers=auth_headers).json()
    assert booking_after["status"] == "CONFIRMED"


def test_webhook_is_idempotent_on_repeated_event(client, auth_headers, seeded_test):
    booking = _make_booking(client, auth_headers, seeded_test)
    payload = {"event_id": "evt_dup", "booking_id": booking["id"], "status": "SUCCESS"}

    first = client.post("/payments/webhook/", json=payload)
    second = client.post("/payments/webhook/", json=payload)
    third = client.post("/payments/webhook/", json=payload)

    assert first.json()["status"] == "processed"
    assert second.json()["status"] == "already_processed"
    assert third.json()["status"] == "already_processed"

    # Only one payment row should exist for the booking, not three.
    booking_after = client.get(f"/bookings/{booking['id']}", headers=auth_headers).json()
    assert booking_after["status"] == "CONFIRMED"


def test_webhook_duplicate_does_not_flip_status_after_cancel(client, auth_headers, seeded_test):
    """A late/duplicate SUCCESS webhook must not resurrect a booking the user already cancelled."""
    booking = _make_booking(client, auth_headers, seeded_test)
    payload = {"event_id": "evt_late", "booking_id": booking["id"], "status": "SUCCESS"}

    client.post("/payments/webhook/", json=payload)
    client.patch(f"/bookings/{booking['id']}/cancel", headers=auth_headers)

    # Same event replayed (simulating a provider retry) after the user cancelled.
    resp = client.post(
        "/payments/webhook/",
        json={"event_id": "evt_late_2", "booking_id": booking["id"], "status": "SUCCESS"},
    )
    assert resp.status_code == 200

    booking_after = client.get(f"/bookings/{booking['id']}", headers=auth_headers).json()
    assert booking_after["status"] == "CANCELLED"


def test_webhook_invalid_booking_id_404(client):
    resp = client.post(
        "/payments/webhook/", json={"event_id": "evt_x", "booking_id": "nope", "status": "SUCCESS"}
    )
    assert resp.status_code == 404


def test_webhook_rejects_malformed_status(client, auth_headers, seeded_test):
    booking = _make_booking(client, auth_headers, seeded_test)
    resp = client.post(
        "/payments/webhook/",
        json={"event_id": "evt_bad", "booking_id": booking["id"], "status": "NOT_A_STATUS"},
    )
    assert resp.status_code == 422
