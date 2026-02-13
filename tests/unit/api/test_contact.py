def test_contact_create_message(client):
    r = client.post(
        "/api/v1/contact",
        json={
            "name": "Test User",
            "email": "user@example.com",
            "subject": "Hello",
            "message": "This is a test message.",
            "hp": "",
            "source": "/contact.html",
        },
    )
    assert r.status_code == 202
    data = r.json()
    assert data["status"] == "received"
    assert isinstance(data.get("id"), str)
    assert len(data["id"]) > 10


def test_contact_honeypot_noop(client):
    r = client.post(
        "/api/v1/contact",
        json={
            "name": "Spambot",
            "email": "bot@example.com",
            "subject": "Buy now",
            "message": "spam spam spam spam spam",
            "hp": "filled",
        },
    )
    assert r.status_code == 202
    data = r.json()
    assert data["status"] == "ok"
    # Honeypot should not return a message id.
    assert data.get("id") in (None, "")

