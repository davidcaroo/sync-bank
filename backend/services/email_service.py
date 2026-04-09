import imaplib
import email
import zipfile
import io
from config import settings
from services.supabase_service import log_email
from services.ingestion_service import ingestion_service, XMLDocument

async def check_emails(search_criteria: str = 'UNSEEN'):
    try:
        prefill_context = await ingestion_service.build_prefill_context(apply_ai=True)

        mail = imaplib.IMAP4_SSL(settings.IMAP_HOST, settings.IMAP_PORT)
        mail.login(settings.IMAP_USER, settings.IMAP_PASS)
        mail.select("inbox")

        status, messages = mail.search(None, search_criteria)
        print(f"IMAP Search: {status}, found {len(messages[0].split())} messages")
        if status != 'OK':
            return

        for num in messages[0].split():
            status, data = mail.fetch(num, '(RFC822)')
            print(f"Fetching message {num}... status: {status}")
            msg = email.message_from_bytes(data[0][1])
            
            email_log = {
                "mensaje_id": msg['Message-ID'],
                "remitente": msg['From'],
                "asunto": msg['Subject'],
                "attachments_encontrados": 0,
                "estado": "procesado"
            }

            for part in msg.walk():
                if part.get_content_maintype() == 'multipart': continue
                if part.get('Content-Disposition') is None: continue
                
                filename = part.get_filename()
                if not filename: continue
                
                content = part.get_payload(decode=True)
                xmls = []

                if filename.endswith('.xml'):
                    xmls.append(content.decode('utf-8'))
                elif filename.endswith('.zip'):
                    with zipfile.ZipFile(io.BytesIO(content)) as z:
                        for zname in z.namelist():
                            if zname.endswith('.xml'):
                                xmls.append(z.read(zname).decode('utf-8'))

                email_log["attachments_encontrados"] += len(xmls)
                
                for xml in xmls:
                    try:
                        result = await ingestion_service.process_xml_document(
                            XMLDocument(file_name=filename, entry_name=filename, xml_text=xml),
                            persist=True,
                            apply_ai=True,
                            categories=prefill_context.get("categories"),
                            cost_centers=prefill_context.get("cost_centers"),
                        )
                        if result.get("status") == "error":
                            email_log["estado"] = "error"
                        
                    except Exception as e:
                        print(f"Error processing XML: {str(e)}")
                        email_log["estado"] = "error"

            try:
                log_email(email_log)
            except Exception as db_err:
                print(f"Error guardando log de email: {db_err}")

            # Mark as read only if it was successfully processed
            if email_log["estado"] == "procesado":
                mail.store(num, '+FLAGS', '\\Seen')

        mail.logout()
    except Exception as e:
        print(f"IMAP Error: {e}")
