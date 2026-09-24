from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from services.auto_causacion_service import (
    AutoCausacionService,
    evaluate_auto_causacion,
)

VALID_CONFIG = {
    "nit_proveedor": "901209021",
    "id_cuenta_alegra": "5105",
    "id_centro_costo_alegra": "12",
    "source": "manual",
    "activo": True,
    "auto_causar": True,
}

VALID_FACTURA = {
    "id": "f1",
    "estado": "pendiente",
    "nit_proveedor": "901209021",
    "nit_receptor": "900741732",
    "xml_raw": "<Invoice/>",
    "cufe": "CUFE-1",
    "numero_factura": "FEUU2183418",
    "moneda": "COP",
    "subtotal": 13900,
    "iva": 0,
    "rete_fuente": 0,
    "rete_ica": 0,
    "rete_iva": 0,
    "total": 13900,
    "items_factura": [
        {
            "total_linea": 13900,
            "cuenta_contable_alegra": "5105",
            "centro_costo_alegra": "12",
        }
    ],
}


def test_valid_invoice_and_rule_are_eligible():
    decision = evaluate_auto_causacion(VALID_FACTURA, VALID_CONFIG)
    assert decision.eligible and decision.reason == "authorized"


@pytest.mark.parametrize(
    "factura_change,config_change,reason",
    [
        ({}, {"activo": False}, "inactive_rule"),
        ({}, {"source": "historical"}, "not_authorized"),
        ({}, {"auto_causar": False}, "not_authorized"),
        ({}, {"id_cuenta_alegra": None}, "missing_account"),
        ({}, {"id_centro_costo_alegra": None}, "missing_cost_center"),
        ({"nit_proveedor": "800000001"}, {}, "nit_mismatch"),
        ({"nit_receptor": "800000001"}, {}, "receiver_nit_mismatch"),
        ({"nit_receptor": None}, {}, "receiver_nit_mismatch"),
        ({"nit_receptor": "123456789"}, {}, "receiver_nit_mismatch"),
        ({"xml_raw": None}, {}, "not_xml"),
        ({"estado": "procesado"}, {}, "not_pending"),
        ({"cufe": "SIN-CUFE"}, {}, "missing_cufe"),
        ({"numero_factura": "SIN-NUMERO"}, {}, "missing_number"),
        ({"moneda": "USD"}, {}, "unsupported_currency"),
        ({"items_factura": []}, {}, "missing_items"),
        ({"total": 0}, {}, "invalid_total"),
        (
            {"items_factura": [{**VALID_FACTURA["items_factura"][0], "centro_costo_alegra": "99"}]},
            {},
            "item_mapping_mismatch",
        ),
        ({"subtotal": 20000}, {}, "line_total_mismatch"),
        ({"iva": 100}, {}, "invoice_total_mismatch"),
    ],
)
def test_each_guard_denies_independently(factura_change, config_change, reason):
    decision = evaluate_auto_causacion(
        {**VALID_FACTURA, **factura_change}, {**VALID_CONFIG, **config_change}
    )
    assert not decision.eligible
    assert decision.reason == reason


def test_missing_rule_is_not_eligible():
    assert evaluate_auto_causacion(VALID_FACTURA, None).reason == "inactive_rule"


def _service(factura=VALID_FACTURA, config=VALID_CONFIG, cause=None, caused_before=None):
    factura_repo = MagicMock()
    factura_repo.get_factura_with_items = AsyncMock(return_value=factura)
    factura_repo.get_successful_causacion = AsyncMock(return_value=caused_before)
    factura_repo.update_factura_fields = AsyncMock()
    config_repo = MagicMock()
    config_repo.get_config_cuenta = AsyncMock(return_value=config)
    causacion_repo = MagicMock()
    causacion_repo.save_causacion = AsyncMock()
    factura_service = MagicMock()
    factura_service.causar_factura = cause or AsyncMock(return_value={"id": "bill-1"})
    service = AutoCausacionService(
        factura_repository=factura_repo,
        config_repository=config_repo,
        causacion_repository=causacion_repo,
        factura_service_=factura_service,
        logger=MagicMock(),
    )
    return service, factura_repo, causacion_repo, factura_service


@pytest.mark.asyncio
async def test_authorized_invoice_is_caused_exactly_once():
    service, _, _, factura_service = _service()

    result = await service.try_cause_from_imap_xml("f1")

    assert result == {"status": "caused", "alegra": {"id": "bill-1"}}
    factura_service.causar_factura.assert_awaited_once_with("f1")


@pytest.mark.asyncio
async def test_provider_without_opt_in_is_never_caused():
    service, _, causacion_repo, factura_service = _service(
        config={**VALID_CONFIG, "auto_causar": False}
    )

    result = await service.try_cause_from_imap_xml("f1")

    assert result["status"] == "skipped"
    factura_service.causar_factura.assert_not_awaited()
    causacion_repo.save_causacion.assert_not_awaited()


@pytest.mark.asyncio
async def test_opted_in_rule_blocked_by_a_guard_stays_pending_with_a_reason():
    service, _, causacion_repo, factura_service = _service(
        factura={**VALID_FACTURA, "moneda": "USD"}
    )

    result = await service.try_cause_from_imap_xml("f1")

    assert result == {"status": "pending", "reason": "unsupported_currency"}
    factura_service.causar_factura.assert_not_awaited()
    saved = causacion_repo.save_causacion.await_args.args[0]
    assert saved["estado"] == "autocausacion_bloqueada"
    assert saved["error_msg"] == "unsupported_currency"


@pytest.mark.asyncio
async def test_alegra_rejection_returns_invoice_to_pending():
    rejection = AsyncMock(
        side_effect=HTTPException(status_code=502, detail={"message": "rechazada"})
    )
    service, factura_repo, causacion_repo, _ = _service(cause=rejection)

    result = await service.try_cause_from_imap_xml("f1")

    assert result == {"status": "pending", "reason": "alegra_error"}
    factura_repo.update_factura_fields.assert_awaited_once_with(
        "f1", {"estado": "pendiente"}
    )
    causacion_repo.save_causacion.assert_awaited_once()


@pytest.mark.asyncio
async def test_unexpected_error_returns_invoice_to_pending():
    boom = AsyncMock(side_effect=RuntimeError("network down"))
    service, factura_repo, _, _ = _service(cause=boom)

    result = await service.try_cause_from_imap_xml("f1")

    assert result["status"] == "pending"
    factura_repo.update_factura_fields.assert_awaited_once_with(
        "f1", {"estado": "pendiente"}
    )


@pytest.mark.asyncio
async def test_duplicate_in_alegra_keeps_invoice_procesado_instead_of_pending():
    duplicate = AsyncMock(
        side_effect=HTTPException(
            status_code=409, detail={"code": "DUPLICADO_ALEGRA", "message": "dup"}
        )
    )
    service, factura_repo, _, _ = _service(cause=duplicate)

    result = await service.try_cause_from_imap_xml("f1")

    assert result == {"status": "skipped", "reason": "duplicado_alegra"}
    factura_repo.update_factura_fields.assert_not_awaited()


@pytest.mark.asyncio
async def test_invoice_with_a_previous_successful_causation_is_not_sent_again():
    service, _, _, factura_service = _service(caused_before={"alegra_bill_id": "9"})

    result = await service.try_cause_from_imap_xml("f1")

    assert result == {"status": "skipped", "reason": "already_caused"}
    factura_service.causar_factura.assert_not_awaited()


@pytest.mark.asyncio
async def test_email_helper_counts_outcomes_and_swallows_failures(monkeypatch):
    from services import email_service

    summary = {"auto_caused": 0, "auto_pending": 0}
    outcomes = iter(
        [
            {"status": "caused"},
            {"status": "pending", "reason": "x"},
            {"status": "skipped"},
            RuntimeError("boom"),
        ]
    )

    async def fake_try(factura_id):
        outcome = next(outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(
        email_service.auto_causacion_service, "try_cause_from_imap_xml", fake_try
    )

    for _ in range(4):
        await email_service._try_auto_causacion("f1", summary)

    assert summary == {"auto_caused": 1, "auto_pending": 1}


def test_parsed_peaje_invoice_passes_the_guard_with_a_devisab_rule(monkeypatch):
    from config import settings
    from peaje_fixture import PEAJE_ATTACHED_DOCUMENT_XML

    monkeypatch.setattr(settings, "COMPANY_NIT", "800123000")
    from services.xml_parser import parse_xml_dian

    parsed = parse_xml_dian(PEAJE_ATTACHED_DOCUMENT_XML)
    factura = {
        **parsed.model_dump(exclude={"items"}),
        "estado": "pendiente",
        "items_factura": [
            {
                **item.model_dump(),
                "cuenta_contable_alegra": "5105",
                "centro_costo_alegra": "12",
            }
            for item in parsed.items
        ],
    }

    decision = evaluate_auto_causacion(factura, VALID_CONFIG)

    assert decision.eligible, decision.reason


def test_autocausation_accepts_the_company_nit_with_a_verification_digit(monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "COMPANY_NIT", "900741732-1")

    assert evaluate_auto_causacion(VALID_FACTURA, VALID_CONFIG).eligible
