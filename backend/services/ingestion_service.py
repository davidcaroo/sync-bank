from services.ingestion.extractor import IngestionExtractor, XMLDocument
from services.ingestion.prefill import IngestionPrefill
from services.ingestion.processor import IngestionProcessor
from repositories.config_repository import (
    get_config_cuenta,
    sync_config_proveedor_nombre,
)
from repositories.factura_repository import find_factura_by_cufe, save_factura
from repositories.db_utils import run_in_executor
from services.xml_parser import parse_xml_dian

class IngestionService:
    def __init__(self) -> None:
        self._extractor = IngestionExtractor()
        self._prefill = IngestionPrefill()

    async def extract_xml_documents_from_upload(self, files) -> list[dict]:
        return await self._extractor.extract_xml_documents_from_upload(files)

    def extract_xml_documents_from_attachment(self, file_name: str, content: bytes) -> dict:
        return self._extractor.extract_xml_documents_from_attachment(file_name, content)

    async def process_xml_document(
        self,
        xml_doc: XMLDocument,
        *,
        persist: bool,
        apply_ai: bool,
        categories: list | None,
        cost_centers: list | None,
        auto_apply_ai: bool = False,
        preview_mode: bool = False,
    ) -> dict:
        processor = IngestionProcessor(
            parse_xml=parse_xml_dian,
            run_in_executor=run_in_executor,
            get_config_cuenta=get_config_cuenta,
            sync_config_proveedor_nombre=sync_config_proveedor_nombre,
            find_factura_by_cufe=find_factura_by_cufe,
            save_factura=save_factura,
        )
        return await processor.process_xml_document(
            xml_doc,
            persist=persist,
            apply_ai=apply_ai,
            categories=categories,
            cost_centers=cost_centers,
            auto_apply_ai=auto_apply_ai,
            preview_mode=preview_mode,
        )

    async def build_prefill_context(self, *, apply_ai: bool) -> dict:
        return await self._prefill.build_prefill_context(apply_ai=apply_ai)

    def _extract_xml_from_zip_bytes(
        self,
        zip_name: str,
        content: bytes,
        *,
        path: str,
        depth: int,
    ) -> tuple[list[XMLDocument], list[dict]]:
        return self._extractor._extract_xml_from_zip_bytes(zip_name, content, path=path, depth=depth)

    def _decode_xml_bytes(self, content: bytes) -> str | None:
        return self._extractor._decode_xml_bytes(content)


ingestion_service = IngestionService()
