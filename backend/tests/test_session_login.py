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
