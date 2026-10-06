import pytest

from services import notifier


class FakeSMTP:
    sent = []
    login_args = None
    fail = False

    def __init__(self, host, port, timeout=None):
        if FakeSMTP.fail:
            raise OSError("smtp down")
        self.host, self.port = host, port

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def login(self, user, password):
        FakeSMTP.login_args = (user, password)

    def send_message(self, message):
        FakeSMTP.sent.append(message)


@pytest.fixture(autouse=True)
def smtp(monkeypatch):
    FakeSMTP.sent = []
    FakeSMTP.login_args = None
    FakeSMTP.fail = False
    notifier._last_sent.clear()
    monkeypatch.setattr(notifier.smtplib, "SMTP_SSL", FakeSMTP)
    monkeypatch.setattr(notifier.settings, "IMAP_USER", "sender@gmail.com")
    monkeypatch.setattr(notifier.settings, "IMAP_PASS", "app-password")
    monkeypatch.setattr(
        notifier.settings, "ALERT_EMAILS", "a@x.com, b@x.com ,"
    )
    monkeypatch.setattr(notifier.settings, "ALERT_COOLDOWN_MINUTES", 360)


@pytest.mark.asyncio
async def test_an_alert_goes_to_every_recipient_from_the_mailbox_account():
    await notifier.notify("k1", "Fallo de sincronizacion", "imap down")

    assert len(FakeSMTP.sent) == 1
    message = FakeSMTP.sent[0]
    assert message["To"] == "a@x.com, b@x.com"
    assert message["From"] == "sender@gmail.com"
    assert "Fallo de sincronizacion" in message["Subject"]
    assert "imap down" in message.get_content()
    assert FakeSMTP.login_args == ("sender@gmail.com", "app-password")


@pytest.mark.asyncio
async def test_the_same_alert_is_not_repeated_within_the_cooldown(monkeypatch):
    await notifier.notify("same", "s", "b")
    await notifier.notify("same", "s", "b")
    await notifier.notify("other", "s", "b")

    assert len(FakeSMTP.sent) == 2

    monkeypatch.setattr(notifier, "_now", lambda: notifier._last_sent["same"] + 361 * 60)
    await notifier.notify("same", "s", "b")
    assert len(FakeSMTP.sent) == 3


@pytest.mark.asyncio
async def test_without_recipients_nothing_is_sent(monkeypatch):
    monkeypatch.setattr(notifier.settings, "ALERT_EMAILS", "")

    await notifier.notify("k", "s", "b")

    assert FakeSMTP.sent == []


@pytest.mark.asyncio
async def test_a_failing_smtp_never_breaks_the_caller_and_can_be_retried():
    FakeSMTP.fail = True

    await notifier.notify("k", "s", "b")

    assert FakeSMTP.sent == []
    FakeSMTP.fail = False
    await notifier.notify("k", "s", "b")
    assert len(FakeSMTP.sent) == 1
