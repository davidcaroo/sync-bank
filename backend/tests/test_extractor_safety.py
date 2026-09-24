import io
import os
import zipfile


from config import settings
from services.ingestion.extractor import IngestionExtractor

CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
INVOICE = (
    f'<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" '
    f'xmlns:cbc="{CBC}"><cbc:ID>F1</cbc:ID></Invoice>'
)
CREDIT_NOTE = (
    f'<CreditNote xmlns="urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2" '
    f'xmlns:cbc="{CBC}"><cbc:ID>NC1</cbc:ID></CreditNote>'
)
EVENT = (
    f'<ApplicationResponse xmlns:cbc="{CBC}"><cbc:ID>E1</cbc:ID></ApplicationResponse>'
)


def attached(inner: str) -> str:
    return (
        '<AttachedDocument xmlns="urn:oasis:names:specification:ubl:schema:xsd:AttachedDocument-2" '
        f'xmlns:cac="{CAC}" xmlns:cbc="{CBC}"><cac:Attachment><cac:ExternalReference>'
        f"<cbc:Description><![CDATA[{inner}]]></cbc:Description>"
        "</cac:ExternalReference></cac:Attachment></AttachedDocument>"
    )


def make_zip(entries: dict[str, bytes | str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def extract(name: str, content: bytes) -> dict:
    return IngestionExtractor().extract_xml_documents_from_attachment(name, content)


def reasons(result: dict) -> str:
    return " | ".join(e["reason"] for e in result["errors"])


def test_a_standalone_invoice_and_an_attached_invoice_are_accepted():
    plain = extract("f.xml", INVOICE.encode())
    wrapped = extract("f.zip", make_zip({"a.xml": attached(INVOICE)}))

    assert len(plain["documents"]) == 1 and plain["errors"] == []
    assert len(wrapped["documents"]) == 1 and wrapped["errors"] == []


def test_dian_events_are_explicitly_ignored_not_reported_as_invalid():
    result = extract("e.zip", make_zip({"e.xml": attached(EVENT), "f.xml": INVOICE}))

    assert [d.entry_name for d in result["documents"]] == ["e.zip/f.xml"]
    assert [e["status"] for e in result["errors"]] == ["ignored"]


def test_credit_notes_are_separated_as_unsupported():
    result = extract("n.xml", CREDIT_NOTE.encode())

    assert result["documents"] == []
    assert result["errors"][0]["status"] == "invalid"
    assert "no soportad" in reasons(result).lower()


def test_an_unknown_xml_root_is_not_treated_as_an_invoice():
    result = extract("x.xml", b"<Random/>")

    assert result["documents"] == [] and "no soportad" in reasons(result).lower()


def test_an_encrypted_zip_is_rejected_before_reading_it():
    data = bytearray(make_zip({"a.xml": INVOICE}))
    data[data.index(b"PK\x03\x04") + 6] |= 1
    data[data.index(b"PK\x01\x02") + 8] |= 1

    result = extract("c.zip", bytes(data))

    assert result["documents"] == [] and "cifrad" in reasons(result).lower()


def test_a_zip_with_too_many_entries_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "MAX_ZIP_ENTRIES", 2)

    result = extract("m.zip", make_zip({f"{i}.xml": INVOICE for i in range(3)}))

    assert result["documents"] == [] and "entradas" in reasons(result).lower()


def test_a_zip_that_expands_beyond_the_limit_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "MAX_ZIP_EXPANDED_BYTES", 1000)
    entries = {f"{i}.xml": os.urandom(600) for i in range(3)}

    result = extract("big.zip", make_zip(entries))

    assert result["documents"] == [] and "descomprim" in reasons(result).lower()


def test_a_zip_bomb_is_rejected_by_its_compression_ratio():
    result = extract("bomb.zip", make_zip({"a.xml": b"0" * (2 * 1024 * 1024)}))

    assert result["documents"] == [] and "compresion" in reasons(result).lower()


def test_deeply_nested_zips_are_rejected():
    blob = make_zip({"a.xml": INVOICE})
    for _ in range(5):
        blob = make_zip({"inner.zip": blob})

    result = extract("nest.zip", blob)

    assert result["documents"] == [] and "profundo" in reasons(result).lower()


def test_an_oversized_attachment_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "MAX_ATTACHMENT_BYTES", 100)

    result = extract("huge.xml", b"<a/>" + b" " * 200)

    assert result["documents"] == [] and "tamano" in reasons(result).lower()
