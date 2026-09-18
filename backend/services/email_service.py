import base64
import imaplib
import email
import hashlib
import logging
import re
from email.header import decode_header
from config import settings
from repositories.logs_repository import upsert_email_log
from repositories.db_utils import run_in_executor
from services.auto_causacion_service import auto_causacion_service
from services.ingestion_service import ingestion_service
from services.pdf_extraction_service import extraer_pdf_from_bytes
from repositories.pending_document_repository import save_pending_document


logger = logging.getLogger("email_service")


def _imap_utf7(text: str) -> str:
    """Encode a mailbox name as IMAP modified UTF-7 (RFC 3501)."""
    out: list[str] = []
    pending: list[str] = []

    def flush() -> None:
        if pending:
            raw = base64.b64encode("".join(pending).encode("utf-16-be")).decode()
            out.append("&" + raw.rstrip("=").replace("/", ",") + "-")
            pending.clear()

    for char in text:
        if 0x20 <= ord(char) <= 0x7E:
            flush()
            out.append("&-" if char == "&" else char)
        else:
            pending.append(char)
    flush()
    return "".join(out)


def _mailbox_arg(name: str) -> str:
    """Mailbox name ready for SELECT: UTF-7 encoded and quoted when needed."""
    encoded = _imap_utf7(name)
    if re.fullmatch(r"[A-Za-z0-9._/\-]+", encoded):
        return encoded
    escaped = encoded.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


async def _try_auto_causacion(factura_id: str, summary: dict) -> None:
    """Opt-in autocausation; never lets a failure affect email processing."""
    try:
        outcome = await auto_causacion_service.try_cause_from_imap_xml(factura_id)
    except Exception:
        logger.exception("auto_causacion_unexpected", extra={"factura_id": factura_id})
        return
    if outcome.get("status") == "caused":
        summary["auto_caused"] += 1
    elif outcome.get("status") == "pending":
        summary["auto_pending"] += 1


def _decode_mime_filename(filename: str | None) -> str:
    if not filename:
        return ""
    try:
        decoded = decode_header(filename)
        parts = []
        for chunk, encoding in decoded:
            if isinstance(chunk, bytes):
                parts.append(chunk.decode(encoding or "utf-8", errors="replace"))
            else:
                parts.append(chunk)
        return "".join(parts)
    except Exception:
        return filename


async def check_emails(search_criteria: str = "UNSEEN"):
    summary = {
        "messages_found": 0,
        "messages_processed": 0,
        "xml_extracted": 0,
        "pdf_candidates": 0,
        "created": 0,
        "auto_caused": 0,
        "auto_pending": 0,
        "duplicates": 0,
        "invalid": 0,
        "errors": 0,
        "invalid_details": [],
    }
    try:
        prefill_context = await ingestion_service.build_prefill_context(apply_ai=False)

        mail = imaplib.IMAP4_SSL(settings.IMAP_HOST, settings.IMAP_PORT)
        mail.login(settings.IMAP_USER, settings.IMAP_PASS)
        mailbox = (settings.IMAP_MAILBOX or "").strip() or "inbox"
        select_status, _ = mail.select(_mailbox_arg(mailbox))
        if select_status != "OK":
            summary["errors"] += 1
            summary["invalid_details"].append(
                {
                    "source": "imap",
                    "asunto": None,
                    "remitente": None,
                    "file_name": mailbox,
                    "entry_name": None,
                    "reason": (
                        f"No se pudo abrir la carpeta o etiqueta '{mailbox}'. "
                        "Verifica el nombre; en Gmail, la etiqueta debe estar "
                        "visible en IMAP (Configuración > Etiquetas > Mostrar en IMAP)."
                    ),
                }
            )
            try:
                mail.logout()
            except Exception:
                pass
            return summary

        status, messages = mail.search(None, search_criteria)
        found_messages = len(messages[0].split())
        summary["messages_found"] = found_messages
        print(f"IMAP Search: {status}, found {found_messages} messages")
        if status != "OK":
            summary["errors"] += 1
            return summary

        for num in messages[0].split():
            status, data = mail.fetch(num, "(RFC822)")
            print(f"Fetching message {num}... status: {status}")
            if status != "OK":
                summary["errors"] += 1
                continue

            msg = email.message_from_bytes(data[0][1])

            email_log = {
                "mensaje_id": msg["Message-ID"],
                "remitente": msg["From"],
                "asunto": msg["Subject"],
                "attachments_encontrados": 0,
                "estado": "ignorado",
            }

            has_relevant_attachment = False
            has_errors = False

            for part in msg.walk():
                if part.get_content_maintype() == "multipart":
                    continue
                if part.get("Content-Disposition") is None:
                    continue

                filename = _decode_mime_filename(part.get_filename()) or "sin_nombre"
                if not filename:
                    continue

                content = part.get_payload(decode=True)
                lower_name = filename.lower()
                if not content:
                    continue

                if not lower_name.endswith((".xml", ".zip", ".pdf")):
                    continue

                has_relevant_attachment = True
                if lower_name.endswith(".pdf"):
                    try:
                        extraction = await extraer_pdf_from_bytes(filename, content)
                        digest = hashlib.sha256(content).hexdigest()
                        for candidate in extraction.get("facturas", []):
                            await run_in_executor(
                                lambda item=candidate: save_pending_document(
                                    {
                                        "message_id": msg["Message-ID"] or digest,
                                        "attachment_sha256": digest,
                                        "file_name": filename,
                                        "page_start": item["page_start"],
                                        "page_end": item["page_end"],
                                        "raw_text": item["raw_text"],
                                        "candidate": item,
                                        "missing_fields": item.get(
                                            "missing_fields", []
                                        ),
                                        "warnings": item.get("warnings", []),
                                    }
                                )
                            )
                            summary["pdf_candidates"] += 1
                        email_log["attachments_encontrados"] += 1
                    except Exception:
                        summary["errors"] += 1
                        has_errors = True
                    continue

                extracted = ingestion_service.extract_xml_documents_from_attachment(
                    filename, content
                )
                documents = extracted.get("documents") or []
                extract_errors = extracted.get("errors") or []

                email_log["attachments_encontrados"] += len(documents)
                summary["xml_extracted"] += len(documents)

                if extract_errors:
                    has_errors = True
                    summary["invalid"] += len(extract_errors)
                    for err in extract_errors:
                        print(
                            f"Error extrayendo XML ({err.get('entry_name')}): {err.get('reason')}"
                        )
                        summary["invalid_details"].append(
                            {
                                "source": "extract",
                                "asunto": msg.get("Subject"),
                                "remitente": msg.get("From"),
                                "file_name": err.get("file_name") or filename,
                                "entry_name": err.get("entry_name"),
                                "reason": err.get("reason") or "Error extrayendo XML.",
                            }
                        )

                for xml_doc in documents:
                    try:
                        result = await ingestion_service.process_xml_document(
                            xml_doc,
                            persist=True,
                            apply_ai=False,
                            categories=prefill_context.get("categories"),
                            cost_centers=prefill_context.get("cost_centers"),
                        )
                        status_result = result.get("status")
                        if status_result == "created":
                            summary["created"] += 1
                            if result.get("factura_id"):
                                await _try_auto_causacion(
                                    str(result["factura_id"]), summary
                                )
                        elif status_result == "duplicate":
                            summary["duplicates"] += 1
                        elif status_result == "invalid":
                            summary["invalid"] += 1
                            has_errors = True
                            summary["invalid_details"].append(
                                {
                                    "source": "parser",
                                    "asunto": msg.get("Subject"),
                                    "remitente": msg.get("From"),
                                    "file_name": result.get("file_name") or filename,
                                    "entry_name": result.get("entry_name")
                                    or xml_doc.entry_name,
                                    "reason": result.get("reason")
                                    or "Documento XML inválido.",
                                }
                            )
                        elif status_result == "error":
                            summary["errors"] += 1
                            has_errors = True
                    except Exception as e:
                        print(f"Error processing XML: {str(e)}")
                        summary["errors"] += 1
                        has_errors = True

            if email_log["attachments_encontrados"] > 0:
                email_log["estado"] = "error" if has_errors else "procesado"
            elif has_relevant_attachment:
                email_log["estado"] = "error" if has_errors else "ignorado"

            try:
                await run_in_executor(lambda: upsert_email_log(email_log))
            except Exception as db_err:
                print(f"Error guardando log de email: {db_err}")
                summary["errors"] += 1

            summary["messages_processed"] += 1

            # Keep payload bounded for API response/UI rendering.
            if len(summary["invalid_details"]) > 100:
                summary["invalid_details"] = summary["invalid_details"][:100]

            # Keep retry for real processing errors; ignore non-processable emails.
            if email_log["estado"] in {"procesado", "ignorado"}:
                mail.store(num, "+FLAGS", "\\Seen")

        mail.logout()
        return summary
    except Exception as e:
        print(f"IMAP Error: {e}")
        summary["errors"] += 1
        return summary
