def test_create_and_list_centre_with_test(client, auth_headers):
    centre = client.post(
        "/centres/", json={"name": "City Diagnostics", "location": "Pune"}, headers=auth_headers
    ).json()
    client.post(
        f"/centres/{centre['id']}/tests",
        json={"name": "Blood Panel", "price": "499.00"},
        headers=auth_headers,
    )

    resp = client.get("/centres/")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "City Diagnostics"
    assert len(data[0]["tests"]) == 1
    assert data[0]["tests"][0]["price"] == "499.00"


def test_get_single_centre(client, auth_headers):
    centre = client.post(
        "/centres/", json={"name": "Metro Labs", "location": "Mumbai"}, headers=auth_headers
    ).json()
    resp = client.get(f"/centres/{centre['id']}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Metro Labs"


def test_get_nonexistent_centre_404(client):
    resp = client.get("/centres/does-not-exist")
    assert resp.status_code == 404


def test_create_centre_requires_auth(client):
    resp = client.post("/centres/", json={"name": "X", "location": "Y"})
    assert resp.status_code in (401, 403)


def test_add_test_to_missing_centre_404(client, auth_headers):
    resp = client.post(
        "/centres/does-not-exist/tests", json={"name": "X", "price": "1.00"}, headers=auth_headers
    )
    assert resp.status_code == 404


def test_add_test_rejects_non_positive_price(client, auth_headers):
    centre = client.post(
        "/centres/", json={"name": "City Diagnostics", "location": "Pune"}, headers=auth_headers
    ).json()
    resp = client.post(
        f"/centres/{centre['id']}/tests", json={"name": "X", "price": "0"}, headers=auth_headers
    )
    assert resp.status_code == 422
