import imaplib
import email
import zipfile
import io
import httpx
from config import settings
from services.xml_parser import parse_xml_dian
from services.supabase_service import log_email, save_factura, get_config_cuenta
from services.ai_service import clasificar_item
from services.alegra_service import alegra_service

async def check_emails():
    try:
        mail = imaplib.IMAP4_SSL(settings.IMAP_HOST, settings.IMAP_PORT)
        mail.login(settings.IMAP_USER, settings.IMAP_PASS)
        mail.select("inbox")

        status, messages = mail.search(None, 'UNSEEN')
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
                        factura = parse_xml_dian(xml)
                        
                        # AI Classification for each item
                        config = get_config_cuenta(factura.nit_proveedor)
                        async with httpx.AsyncClient() as client:
                            categories = await alegra_service.get_categories(client)
                            cost_centers = await alegra_service.get_cost_centers(client)
                            
                        for item in factura.items:
                            if config:
                                item.cuenta_contable_alegra = config["id_cuenta_alegra"]
                                item.centro_costo_alegra = config.get("id_centro_costo_alegra")
                            else:
                                # Fallback to AI with real categories and cost centers
                                classification = await clasificar_item(item.descripcion, categories, cost_centers)
                                item.cuenta_contable_alegra = classification.get("cuenta_id")
                                item.centro_costo_alegra = classification.get("centro_costo_id")

                        # Save to Supabase
                        save_factura(factura.model_dump(exclude={"items"}, mode="json"), [i.model_dump(mode="json") for i in factura.items])
                        
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
