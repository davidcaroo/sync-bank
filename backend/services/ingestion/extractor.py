import io
import zipfile
from dataclasses import dataclass


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

    def extract_xml_documents_from_attachment(self, file_name: str, content: bytes) -> dict:
        name = file_name or "sin_nombre"
        lower_name = name.lower()

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
            return {
                "documents": [XMLDocument(file_name=name, entry_name=name, xml_text=xml_text)],
                "errors": [],
            }

        if lower_name.endswith(".zip"):
            docs, errs = self._extract_xml_from_zip_bytes(name, content, path=name, depth=0)
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
                            documents.append(
                                XMLDocument(file_name=zip_name, entry_name=nested_path, xml_text=xml_text)
                            )
                            continue

                        if lower_entry.endswith(".zip"):
                            nested_docs, nested_errors = self._extract_xml_from_zip_bytes(
                                zip_name,
                                entry_bytes,
                                path=nested_path,
                                depth=depth + 1,
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

    def _decode_xml_bytes(self, content: bytes) -> str | None:
        for encoding in ("utf-8-sig", "utf-8", "utf-16", "utf-16-le", "utf-16-be", "latin-1"):
            try:
                return content.decode(encoding)
            except Exception:
                continue
        return None