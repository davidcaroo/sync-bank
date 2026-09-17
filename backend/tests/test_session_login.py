from fastapi.testclient import TestClient

import main


def test_browser_is_redirected_to_login_and_can_start_session(monkeypatch):
    monkeypatch.setattr(main, "open_pool", lambda: None)
    monkeypatch.setattr(main, "close_pool", lambda: None)
    monkeypatch.setattr(main, "start_scheduler", lambda: None)

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
