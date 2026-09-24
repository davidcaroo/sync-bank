import io
import zipfile
from dataclasses import dataclass

from config import settings
from services.xml_parser import classify_xml


@dataclass
class XMLDocument:
    file_name: str
    entry_name: str
    xml_text: str


class IngestionExtractor:
    async def extract_xml_documents_from_upload(self, files) -> dict:
        documents: list[XMLDocument] = []
        errors: list[dict] = []

        for file in files or []:
            filename = file.filename or "sin_nombre"

            try:
                content = await file.read()
            except Exception as exc:
                errors.append(
                    {
                        "file_name": filename,
                        "entry_name": filename,
                        "status": "invalid",
                        "reason": f"No se pudo leer archivo: {exc}",
                    }
                )
                continue

            extracted = self.extract_xml_documents_from_attachment(filename, content)
            documents.extend(extracted.get("documents") or [])
            errors.extend(extracted.get("errors") or [])

        return {
            "documents": documents,
            "errors": errors,
        }

    def extract_xml_documents_from_attachment(
        self, file_name: str, content: bytes
    ) -> dict:
        name = file_name or "sin_nombre"
        lower_name = name.lower()

        if len(content) > settings.MAX_ATTACHMENT_BYTES:
            return {
                "documents": [],
                "errors": [
                    {
                        "file_name": name,
                        "entry_name": name,
                        "status": "invalid",
                        "reason": "Adjunto excede el tamano maximo permitido.",
                    }
                ],
            }

        if lower_name.endswith(".xml"):
            xml_text = self._decode_xml_bytes(content)
            if xml_text is None:
                return {
                    "documents": [],
                    "errors": [
                        {
                            "file_name": name,
                            "entry_name": name,
                            "status": "invalid",
                            "reason": "No se pudo decodificar XML.",
                        }
                    ],
                }
            documents: list[XMLDocument] = []
            errors: list[dict] = []
            self._accept(documents, errors, name, name, xml_text)
            return {"documents": documents, "errors": errors}

        if lower_name.endswith(".zip"):
            docs, errs = self._extract_xml_from_zip_bytes(
                name, content, path=name, depth=0
            )
            if not docs and not errs:
                errs.append(
                    {
                        "file_name": name,
                        "entry_name": name,
                        "status": "invalid",
                        "reason": "ZIP sin XML procesables.",
                    }
                )
            return {
                "documents": docs,
                "errors": errs,
            }

            if lower_name.endswith(".pdf"):
                return {
                    "documents": [],
                    "errors": [
                        {
                            "file_name": name,
                            "entry_name": name,
                            "status": "invalid",
                            "reason": "PDF no soportado en este endpoint. Usa /extraer-pdf en ai-service.",
                        }
                    ],
                }

        return {
            "documents": [],
            "errors": [
                {
                    "file_name": name,
                    "entry_name": name,
                    "status": "invalid",
                    "reason": "Tipo de archivo no soportado. Solo .xml y .zip",
                }
            ],
        }

    def _extract_xml_from_zip_bytes(
        self,
        zip_name: str,
        content: bytes,
        *,
        path: str,
        depth: int,
    ) -> tuple[list[XMLDocument], list[dict]]:
        documents: list[XMLDocument] = []
        errors: list[dict] = []

        if depth > 3:
            return documents, [
                {
                    "file_name": zip_name,
                    "entry_name": path,
                    "status": "invalid",
                    "reason": "ZIP anidado demasiado profundo.",
                }
            ]

        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zipped:
                problem = self._zip_problem(zipped.infolist())
                if problem:
                    return documents, [
                        {
                            "file_name": zip_name,
                            "entry_name": path,
                            "status": "invalid",
                            "reason": problem,
                        }
                    ]
                for entry_name in zipped.namelist():
                    lower_entry = entry_name.lower()
                    try:
                        entry_bytes = zipped.read(entry_name)
                        nested_path = f"{path}/{entry_name}"

                        if lower_entry.endswith(".xml"):
                            xml_text = self._decode_xml_bytes(entry_bytes)
                            if xml_text is None:
                                errors.append(
                                    {
                                        "file_name": zip_name,
                                        "entry_name": nested_path,
                                        "status": "invalid",
                                        "reason": "No se pudo decodificar XML dentro del ZIP.",
                                    }
                                )
                                continue
                            self._accept(
                                documents, errors, zip_name, nested_path, xml_text
                            )
                            continue

                        if lower_entry.endswith(".zip"):
                            nested_docs, nested_errors = (
                                self._extract_xml_from_zip_bytes(
                                    zip_name,
                                    entry_bytes,
                                    path=nested_path,
                                    depth=depth + 1,
                                )
                            )
                            documents.extend(nested_docs)
                            errors.extend(nested_errors)
                    except Exception as exc:
                        errors.append(
                            {
                                "file_name": zip_name,
                                "entry_name": f"{path}/{entry_name}",
                                "status": "invalid",
                                "reason": f"Error leyendo XML dentro de ZIP: {exc}",
                            }
                        )
        except Exception as exc:
            errors.append(
                {
                    "file_name": zip_name,
                    "entry_name": path,
                    "status": "invalid",
                    "reason": f"ZIP invalido: {exc}",
                }
            )

        return documents, errors

    @staticmethod
    def _zip_problem(infos) -> str | None:
        """Checked from ZIP metadata alone, before decompressing anything."""
        if len(infos) > settings.MAX_ZIP_ENTRIES:
            return "ZIP con demasiadas entradas."
        if any(info.flag_bits & 0x1 for info in infos):
            return "ZIP cifrado no soportado."
        if sum(info.file_size for info in infos) > settings.MAX_ZIP_EXPANDED_BYTES:
            return "ZIP excede el tamano maximo descomprimido."
        for info in infos:
            if info.file_size and (
                not info.compress_size
                or info.file_size / info.compress_size
                > settings.MAX_ZIP_COMPRESSION_RATIO
            ):
                return "ZIP con relacion de compresion sospechosa."
        return None

    @staticmethod
    def _accept(documents, errors, file_name, entry_name, xml_text) -> None:
        kind = classify_xml(xml_text)
        if kind == "invoice":
            documents.append(XMLDocument(file_name, entry_name, xml_text))
            return
        if kind == "event":
            status, reason = "ignored", "Evento DIAN ignorado: no es una factura."
        elif kind in ("credit_note", "debit_note"):
            status, reason = "invalid", "Nota credito/debito no soportada."
        else:
            status, reason = "invalid", "Documento XML no soportado (no es una factura DIAN)."
        errors.append(
            {
                "file_name": file_name,
                "entry_name": entry_name,
                "status": status,
                "reason": reason,
            }
        )

    def _decode_xml_bytes(self, content: bytes) -> str | None:
        for encoding in (
            "utf-8-sig",
            "utf-8",
            "utf-16",
            "utf-16-le",
            "utf-16-be",
            "latin-1",
        ):
            try:
                return content.decode(encoding)
            except Exception:
                continue
        return None
