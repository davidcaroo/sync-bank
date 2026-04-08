import imaplib
import email
import zipfile
import io
import httpx
from config import settings
from services.xml_parser import parse_xml_dian
from services.supabase_service import log_email, save_factura, get_config_cuenta, sync_config_proveedor_nombre
from services.ai_service import clasificar_item
from services.alegra_service import alegra_service

async def check_emails(search_criteria: str = 'UNSEEN'):
    try:
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
                        factura = parse_xml_dian(xml)
                        sync_config_proveedor_nombre(factura.nit_proveedor, factura.nombre_proveedor)
                        requires_manual_review = False
                        
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
                                confidence = float(classification.get("confianza") or 0.0)
                                if confidence < settings.AI_CONFIDENCE_THRESHOLD:
                                    requires_manual_review = True
                                    item.cuenta_contable_alegra = None
                                    item.centro_costo_alegra = None
                                else:
                                    item.cuenta_contable_alegra = classification.get("cuenta_id")
                                    item.centro_costo_alegra = classification.get("centro_costo_id")

                        factura_payload = factura.model_dump(exclude={"items"}, mode="json")
                        # The current DB constraint does not include "pendiente_revision".
                        # We keep invoice state as "pendiente" and enforce manual confirmation
                        # later based on missing account assignments on items.
                        factura_payload["estado"] = "pendiente"

                        # Save to Supabase
                        save_result = save_factura(
                            factura_payload,
                            [i.model_dump(mode="json") for i in factura.items],
                        )
                        if save_result.get("duplicado"):
                            # logs_email currently allows only known states; keep it as processed.
                            email_log["estado"] = "procesado"
                        
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
