from app import Profile, db


def _login(client):
    with client.session_transaction() as sess:
        sess["logged_in"] = True


def test_phone_saved_from_profile_form(client, portfolio_app):
    _login(client)
    form = client.get("/admin/profile").get_data(as_text=True)
    assert 'name="phone"' in form

    client.post("/admin/profile", data={"name": "박종걸", "email": "test@example.com",
                                        "phone": " 010-1234-5678 "})
    with portfolio_app.app_context():
        assert db.session.get(Profile, 1).phone == "010-1234-5678"


def test_phone_card_shows_on_public_page_with_tel_link(client, portfolio_app):
    with portfolio_app.app_context():
        db.session.get(Profile, 1).phone = "010-1234-5678"
        db.session.commit()

    html = client.get("/").get_data(as_text=True)
    assert 'href="tel:01012345678"' in html
    assert 'data-convert="phone"' in html
    assert "010-1234-5678" in html
    assert "Phone" in client.get("/en").get_data(as_text=True)


def test_phone_card_hidden_when_empty(client):
    assert 'data-convert="phone"' not in client.get("/").get_data(as_text=True)
