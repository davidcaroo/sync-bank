import time
import logging
import asyncio
from typing import Optional

from repositories.factura_repository import list_provider_nits
from repositories.db_utils import run_in_executor
from services.provider_mapping.extractor import HistoricalExtractor, AlegraExtractor
from services.provider_mapping.evaluator import evaluate_account_choice
from services.provider_mapping.persistor import MappingPersistor


class ProviderMappingService:
    """Compute most frequent account for a provider (by NIT) using local history
    and persist it into `config_cuentas` when confidence is high enough.
    """

    MIN_OCCURRENCES = 3
    MIN_SHARE = 0.7

    MAX_PAGES = 10
    PAGE_SIZE = 30
    MAX_BILLS = 300

    BREAKER_THRESHOLD = 3
    BREAKER_COOLDOWN_SEC = 300

    def __init__(self):
        self._historical = HistoricalExtractor()
        self._alegra = AlegraExtractor()
        self._persistor = MappingPersistor()
        self._logger = logging.getLogger("provider-mapping")
        self._alegra_failures = 0
        self._alegra_block_until = 0.0

    def _allow_alegra(self) -> bool:
        return time.time() >= self._alegra_block_until

    def _register_alegra_failure(self):
        self._alegra_failures += 1
        if self._alegra_failures >= self.BREAKER_THRESHOLD:
            self._alegra_block_until = time.time() + self.BREAKER_COOLDOWN_SEC

    def _register_alegra_success(self):
        self._alegra_failures = 0
        self._alegra_block_until = 0.0

    async def _fetch_alegra_with_backoff(self, nit_proveedor: str):
        delays = [0.5, 1.0, 2.0]
        last_exc = None
        for idx, delay in enumerate(delays):
            try:
                return await self._alegra.get_account_counts(
                    nit_proveedor,
                    max_pages=self.MAX_PAGES,
                    page_size=self.PAGE_SIZE,
                    max_bills=self.MAX_BILLS,
                )
            except Exception as exc:
                last_exc = exc
                if idx < len(delays) - 1:
                    await asyncio.sleep(delay)
        raise last_exc

    def _log_metrics(self, *, nit: str, source: str, total: int, share: float, elapsed_ms: float, saved: bool):
        self._logger.info(
            "provider_mapping",
            extra={
                "nit": nit,
                "source": source,
                "total": total,
                "share": round(share, 3),
                "elapsed_ms": round(elapsed_ms, 2),
                "saved": saved,
            },
        )

    async def compute_and_save_mapping(self, nit_proveedor: str, nombre_proveedor: str | None = None) -> Optional[dict]:
        if not nit_proveedor:
            return None

        start = time.perf_counter()

        # 1) Historical extraction
        try:
            counter, total = await self._historical.get_account_counts(nit_proveedor)
        except Exception as exc:
            self._logger.error("historical_extraction_failed", extra={"nit": nit_proveedor, "error": str(exc)})
            counter, total = None, 0

        if counter and total > 0:
            decision = evaluate_account_choice(
                counter,
                total,
                min_occurrences=self.MIN_OCCURRENCES,
                min_share=self.MIN_SHARE,
            )
            if decision:
                saved = await self._persistor.save_mapping(
                    nit_proveedor=nit_proveedor,
                    nombre_proveedor=nombre_proveedor,
                    cuenta=decision["cuenta"],
                    share=decision["share"],
                    source="historical",
                )
                elapsed = (time.perf_counter() - start) * 1000
                self._log_metrics(
                    nit=nit_proveedor,
                    source="historical",
                    total=decision["total"],
                    share=decision["share"],
                    elapsed_ms=elapsed,
                    saved=bool(saved),
                )
                return {
                    "nit": nit_proveedor,
                    "cuenta": decision["cuenta"],
                    "confidence": decision["share"],
                    "saved": bool(saved),
                    "source": "historical",
                    "metrics": {
                        "elapsed_ms": round(elapsed, 2),
                        "total": decision["total"],
                    },
                }

        # 2) Alegra extraction with circuit breaker + backoff
        if not self._allow_alegra():
            return None

        try:
            counter, total = await self._fetch_alegra_with_backoff(nit_proveedor)
            self._register_alegra_success()
        except Exception as exc:
            self._register_alegra_failure()
            self._logger.error("alegra_extraction_failed", extra={"nit": nit_proveedor, "error": str(exc)})
            return None

        if counter and total > 0:
            decision = evaluate_account_choice(
                counter,
                total,
                min_occurrences=self.MIN_OCCURRENCES,
                min_share=self.MIN_SHARE,
            )
            if decision:
                saved = await self._persistor.save_mapping(
                    nit_proveedor=nit_proveedor,
                    nombre_proveedor=nombre_proveedor,
                    cuenta=decision["cuenta"],
                    share=decision["share"],
                    source="alegra",
                )
                elapsed = (time.perf_counter() - start) * 1000
                self._log_metrics(
                    nit=nit_proveedor,
                    source="alegra",
                    total=decision["total"],
                    share=decision["share"],
                    elapsed_ms=elapsed,
                    saved=bool(saved),
                )
                return {
                    "nit": nit_proveedor,
                    "cuenta": decision["cuenta"],
                    "confidence": decision["share"],
                    "saved": bool(saved),
                    "source": "alegra",
                    "metrics": {
                        "elapsed_ms": round(elapsed, 2),
                        "total": decision["total"],
                    },
                }

        return None

    async def suggest_mapping_from_history(
        self,
        nit_proveedor: str,
        *,
        min_occurrences: int = 2,
        min_share: float = 0.6,
    ) -> Optional[dict]:
        """Return a non-persistent historical suggestion for a provider.

        This is less strict than the persisted mapping thresholds and is intended
        for preview/autocomplete suggestions before upload/causation.
        """
        if not nit_proveedor:
            return None

        try:
            counter, total = await self._historical.get_account_counts(nit_proveedor)
        except Exception as exc:
            self._logger.error("historical_suggestion_failed", extra={"nit": nit_proveedor, "error": str(exc)})
            return None

        if not counter or total <= 0:
            return None

        decision = evaluate_account_choice(
            counter,
            total,
            min_occurrences=min_occurrences,
            min_share=min_share,
        )
        if not decision:
            return None

        return {
            "nit": nit_proveedor,
            "cuenta": decision["cuenta"],
            "confidence": decision["share"],
            "source": "historical_suggestion",
            "metrics": {
                "total": decision["total"],
                "count": decision["count"],
            },
        }

    async def recompute_all_mappings(
        self,
        *,
        start_index: int = 0,
        batch_size: int = 100,
        max_concurrency: int = 5,
    ) -> dict:
        """Scan distinct provider NITs and compute mappings in batches.

        Returns a payload with results and the next cursor index.
        """
        results = []
        try:
            nits = await run_in_executor(lambda: list_provider_nits())
        except Exception as exc:
            self._logger.error("list_nits_failed", extra={"error": str(exc)})
            return {
                "results": results,
                "next_index": start_index,
                "total": 0,
                "batch_size": 0,
            }

        total = len(nits)
        if total == 0:
            return {"results": results, "next_index": 0, "total": 0, "batch_size": 0}

        if start_index >= total:
            start_index = 0

        batch = nits[start_index : start_index + batch_size]

        sem = asyncio.Semaphore(max_concurrency)

        async def _process(nit: str):
            async with sem:
                try:
                    out = await self.compute_and_save_mapping(nit, None)
                    return {"nit": nit, "result": out}
                except Exception as exc:
                    return {"nit": nit, "error": str(exc)}

        tasks = [asyncio.create_task(_process(nit)) for nit in batch]
        for item in await asyncio.gather(*tasks):
            results.append(item)

        next_index = start_index + len(batch)
        if next_index >= total:
            next_index = 0

        return {
            "results": results,
            "next_index": next_index,
            "total": total,
            "batch_size": len(batch),
        }


provider_mapping_service = ProviderMappingService()
