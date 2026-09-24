import pytest

from services import email_service
from services.email_service import _imap_utf7, _mailbox_arg


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Facturas", "Facturas"),
        ("Facturación", "Facturaci&APM-n"),
        ("Cuentas & Cobros", "Cuentas &- Cobros"),
        ("Año/2026", "A&APE-o/2026"),
    ],
)
def test_mailbox_names_use_imap_modified_utf7(name, expected):
    assert _imap_utf7(name) == expected


@pytest.mark.parametrize(
    "name,expected",
    [
        ("inbox", "inbox"),
        ("Facturas", "Facturas"),
        ("Facturas/2026", "Facturas/2026"),
        ("Mis Facturas", '"Mis Facturas"'),
        ("[Gmail]/Todos", '"[Gmail]/Todos"'),
        ('Con "comillas"', '"Con \\"comillas\\""'),
    ],
)
def test_mailbox_names_are_quoted_only_when_needed(name, expected):
    assert _mailbox_arg(name) == expected


class FakeImap:
    instances = []

    def __init__(self, host, port, select_status="OK"):
        self.selected = []
        self.searched = 0
        self.logged_out = False
        self.select_status = FakeImap.next_select_status
        FakeImap.instances.append(self)

    next_select_status = "OK"

    def login(self, user, password):
        return "OK", []

    def select(self, mailbox):
        self.selected.append(mailbox)
        return self.select_status, [b"1"]

    def search(self, charset, criteria):
        self.searched += 1
        return "OK", [b""]

    def logout(self):
        self.logged_out = True


@pytest.fixture
def imap(monkeypatch):
    FakeImap.instances = []
    FakeImap.next_select_status = "OK"

    async def no_context(*, apply_ai):
        return {}

    monkeypatch.setattr(email_service.imaplib, "IMAP4_SSL", FakeImap)
    monkeypatch.setattr(email_service.ingestion_service, "build_prefill_context", no_context)
    return FakeImap


@pytest.mark.asyncio
async def test_default_mailbox_is_inbox(imap, monkeypatch):
    monkeypatch.setattr(email_service.settings, "IMAP_MAILBOX", "inbox")

    await email_service.check_emails()

    assert imap.instances[0].selected == ["inbox"]


@pytest.mark.asyncio
async def test_configured_label_is_the_only_mailbox_read(imap, monkeypatch):
    monkeypatch.setattr(email_service.settings, "IMAP_MAILBOX", "Mis Facturas")

    summary = await email_service.check_emails(search_criteria="ALL")

    assert imap.instances[0].selected == ['"Mis Facturas"']
    assert imap.instances[0].searched == 1
    assert summary["errors"] == 0


@pytest.mark.asyncio
async def test_blank_setting_falls_back_to_inbox(imap, monkeypatch):
    monkeypatch.setattr(email_service.settings, "IMAP_MAILBOX", "  ")

    await email_service.check_emails()

    assert imap.instances[0].selected == ["inbox"]


@pytest.mark.asyncio
async def test_missing_label_reports_a_clear_error_and_reads_nothing(imap, monkeypatch):
    monkeypatch.setattr(email_service.settings, "IMAP_MAILBOX", "Facturaz")
    imap.next_select_status = "NO"

    summary = await email_service.check_emails()

    assert summary["errors"] == 1
    assert summary["messages_found"] == 0
    detail = summary["invalid_details"][0]
    assert detail["source"] == "imap" and "Facturaz" in detail["reason"]
    assert "Mostrar en IMAP" in detail["reason"]
    assert imap.instances[0].searched == 0
    assert imap.instances[0].logged_out is True


@pytest.mark.asyncio
async def test_an_unopenable_mailbox_is_reported_as_a_fatal_error(imap, monkeypatch):
    monkeypatch.setattr(email_service.settings, "IMAP_MAILBOX", "NoExiste")
    imap.next_select_status = "NO"

    summary = await email_service.check_emails()

    assert "NoExiste" in summary["fatal_error"]


@pytest.mark.asyncio
async def test_an_imap_connection_failure_is_reported_as_a_fatal_error(monkeypatch):
    class Broken:
        def __init__(self, *args, **kwargs):
            raise OSError("connection refused")

    monkeypatch.setattr(email_service.imaplib, "IMAP4_SSL", Broken)

    async def no_context(*, apply_ai):
        return {}

    monkeypatch.setattr(
        email_service.ingestion_service, "build_prefill_context", no_context
    )

    summary = await email_service.check_emails()

    assert "connection refused" in summary["fatal_error"]


class OneMessageImap:
    def __init__(self, *args, **kwargs):
        self.seen = []

    def login(self, user, password):
        return "OK", []

    def select(self, mailbox):
        return "OK", [b"1"]

    def search(self, charset, criteria):
        return "OK", [b"1"]

    def fetch(self, num, parts):
        from email.message import EmailMessage

        from tests.test_extractor_safety import EVENT, attached, make_zip

        msg = EmailMessage()
        msg["Message-ID"] = "<event@x>"
        msg["From"] = "no-responder@facture.co"
        msg["Subject"] = "Evento"
        msg.set_content("adjunto")
        msg.add_attachment(
            make_zip({"evento.xml": attached(EVENT)}),
            maintype="application",
            subtype="zip",
            filename="evento.zip",
        )
        return "OK", [(b"1", msg.as_bytes())]

    def store(self, num, command, flags):
        self.seen.append(num)

    def logout(self):
        pass


@pytest.mark.asyncio
async def test_dian_events_are_counted_as_ignored_and_the_mail_is_marked_read(monkeypatch):
    logs = []

    async def no_context(*, apply_ai):
        return {}

    monkeypatch.setattr(email_service.imaplib, "IMAP4_SSL", OneMessageImap)
    monkeypatch.setattr(
        email_service.ingestion_service, "build_prefill_context", no_context
    )
    monkeypatch.setattr(email_service, "upsert_email_log", lambda log: logs.append(log))

    summary = await email_service.check_emails()

    assert summary["ignored"] == 1
    assert summary["invalid"] == 0 and summary["errors"] == 0
    assert logs[0]["estado"] == "ignorado"


class CreditNoteImap(OneMessageImap):
    def fetch(self, num, parts):
        from email.message import EmailMessage

        from tests.test_extractor_safety import CREDIT_NOTE, make_zip

        msg = EmailMessage()
        msg["Message-ID"] = "<nc@x>"
        msg["From"] = "no-responder@facture.co"
        msg["Subject"] = "Nota credito"
        msg.set_content("adjunto")
        msg.add_attachment(
            make_zip({"nc.xml": CREDIT_NOTE}),
            maintype="application",
            subtype="zip",
            filename="nc.zip",
        )
        return "OK", [(b"1", msg.as_bytes())]


@pytest.mark.asyncio
async def test_a_deterministically_rejected_mail_is_marked_read_not_retried_forever(
    monkeypatch,
):
    instances = []

    class Tracked(CreditNoteImap):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            instances.append(self)

    async def no_context(*, apply_ai):
        return {}

    monkeypatch.setattr(email_service.imaplib, "IMAP4_SSL", Tracked)
    monkeypatch.setattr(
        email_service.ingestion_service, "build_prefill_context", no_context
    )
    monkeypatch.setattr(email_service, "upsert_email_log", lambda log: None)

    summary = await email_service.check_emails()

    assert summary["invalid"] == 1
    assert instances[0].seen == [b"1"]


@pytest.mark.asyncio
async def test_imap_work_runs_off_the_event_loop_thread(monkeypatch):
    import threading

    main_thread = threading.get_ident()
    threads = []

    class Spy(OneMessageImap):
        def login(self, user, password):
            threads.append(threading.get_ident())
            return super().login(user, password)

        def search(self, charset, criteria):
            threads.append(threading.get_ident())
            return super().search(charset, criteria)

        def fetch(self, num, parts):
            threads.append(threading.get_ident())
            return super().fetch(num, parts)

    async def no_context(*, apply_ai):
        return {}

    monkeypatch.setattr(email_service.imaplib, "IMAP4_SSL", Spy)
    monkeypatch.setattr(
        email_service.ingestion_service, "build_prefill_context", no_context
    )
    monkeypatch.setattr(email_service, "upsert_email_log", lambda log: None)

    await email_service.check_emails()

    assert threads and all(t != main_thread for t in threads)
