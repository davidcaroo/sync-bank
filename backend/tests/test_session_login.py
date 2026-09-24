from fastapi.testclient import TestClient

import main


def test_browser_is_redirected_to_login_and_can_start_session(monkeypatch):
    monkeypatch.setattr(main, "open_pool", lambda: None)
    monkeypatch.setattr(main, "close_pool", lambda: None)
    monkeypatch.setattr(main, "start_scheduler", lambda: None)
    monkeypatch.setattr(main, "apply_schema_upgrades", lambda: None)

    with TestClient(main.app, follow_redirects=False) as client:
        response = client.get("/")
        assert response.status_code == 307
        assert response.headers["location"] == "/login"

        login = client.post(
            "/login",
            data={"username": "admin", "password": "test"},
            follow_redirects=False,
        )
        assert login.status_code == 303
        assert login.headers["location"] == "/"
        assert "syncbank_session=" in login.headers["set-cookie"]


def _client(monkeypatch):
    monkeypatch.setattr(main, "open_pool", lambda: None)
    monkeypatch.setattr(main, "close_pool", lambda: None)
    monkeypatch.setattr(main, "start_scheduler", lambda: None)
    monkeypatch.setattr(main, "apply_schema_upgrades", lambda: None)
    return TestClient(main.app, follow_redirects=False)


def test_login_page_is_self_contained_and_accessible(monkeypatch):
    with _client(monkeypatch) as client:
        page = client.get("/login")

    assert page.status_code == 200
    html = page.text
    assert "Bienvenido de nuevo" in html
    assert 'name="username"' in html and 'name="password"' in html
    assert 'for="username"' in html and 'for="password"' in html
    assert "{{" not in html
    # The middleware redirects every non-public path to /login, so the page must
    # not depend on server-hosted assets.
    assert 'src="/' not in html and 'href="/' not in html


def test_wrong_credentials_show_an_error_and_keep_the_escaped_username(monkeypatch):
    with _client(monkeypatch) as client:
        response = client.post(
            "/login", data={"username": '"><script>x</script>', "password": "nope"}
        )

    assert response.status_code == 401
    assert 'role="alert"' in response.text and "Credenciales incorrectas" in response.text
    assert "<script>x</script>" not in response.text
    assert "&lt;script&gt;x&lt;/script&gt;" in response.text


def _fake_google(monkeypatch, email, verified=True):
    import base64
    import json

    claims = base64.urlsafe_b64encode(
        json.dumps({"email": email, "email_verified": verified}).encode()
    ).decode()

    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"id_token": f"h.{claims}.s"}

    monkeypatch.setattr(main.httpx, "post", lambda *a, **k: Resp())
    monkeypatch.setattr(main.settings, "GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setattr(main.settings, "GOOGLE_CLIENT_SECRET", "secret")
    monkeypatch.setattr(main.settings, "IMAP_USER", "Facturas@Gmail.com")


def test_google_login_allows_the_invoice_mailbox_and_shows_button(monkeypatch):
    _fake_google(monkeypatch, "facturas@gmail.com")
    with _client(monkeypatch) as client:
        assert "Continuar con Google" in client.get("/login").text
        start = client.get("/login/google")
        assert start.headers["location"].startswith("https://accounts.google.com/")
        state = client.cookies.get("syncbank_oauth_state")
        done = client.get(f"/login/google/callback?code=abc&state={state}")
        assert done.status_code == 303
        assert client.get("/").status_code == 200


def test_google_login_rejects_other_emails_and_bad_state(monkeypatch):
    _fake_google(monkeypatch, "intruso@gmail.com")
    with _client(monkeypatch) as client:
        client.get("/login/google")
        state = client.cookies.get("syncbank_oauth_state")
        assert client.get(f"/login/google/callback?code=a&state={state}").status_code == 403
        assert client.get("/login/google/callback?code=a&state=wrong").status_code == 401
