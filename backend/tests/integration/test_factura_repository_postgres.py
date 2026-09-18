from decimal import Decimal

import pytest

from repositories.factura_repository import (
    find_factura_by_cufe,
    list_confirmed_provider_mappings,
    save_causacion,
    save_factura,
)


def test_save_factura_inserts_invoice_and_items():
    result = save_factura(
        {
            "cufe": "CUFE-ATOMIC-1",
            "numero_factura": "FE-1",
            "estado": "pendiente",
            "total": Decimal("119.00"),
        },
        [
            {
                "descripcion": "Servicio",
                "cantidad": Decimal("1"),
                "precio_unitario": Decimal("100.00"),
                "total_linea": Decimal("100.00"),
            }
        ],
    )

    assert result["duplicado"] is False
    assert find_factura_by_cufe("CUFE-ATOMIC-1")["numero_factura"] == "FE-1"


def test_save_factura_returns_existing_for_duplicate_cufe():
    first = save_factura(
        {
            "cufe": "CUFE-DUP-1",
            "numero_factura": "FE-2",
            "estado": "pendiente",
            "total": Decimal("10.00"),
        },
        [],
    )
    second = save_factura(
        {
            "cufe": "CUFE-DUP-1",
            "numero_factura": "FE-3",
            "estado": "pendiente",
            "total": Decimal("20.00"),
        },
        [],
    )

    assert second == {"factura_id": first["factura_id"], "duplicado": True}


def test_save_factura_rolls_back_when_an_item_is_invalid():
    with pytest.raises(Exception):
        save_factura(
            {
                "cufe": "CUFE-ROLLBACK-1",
                "numero_factura": "FE-4",
                "estado": "pendiente",
            },
            [{"descripcion": "Inválido", "cantidad": "no-es-numero"}],
        )

    assert find_factura_by_cufe("CUFE-ROLLBACK-1") is None


def _saved_invoice(cufe, nit, items, causacion_estado=None, estado="pendiente"):
    result = save_factura(
        {
            "cufe": cufe,
            "numero_factura": cufe,
            "nit_proveedor": nit,
            "estado": estado,
            "total": Decimal("10.00"),
        },
        items,
    )
    if causacion_estado:
        save_causacion(
            {
                "factura_id": result["factura_id"],
                "alegra_bill_id": None,
                "alegra_response": {},
                "estado": causacion_estado,
                "intentos": 1,
                "error_msg": None,
            }
        )
    return result["factura_id"]


def _item(cuenta, centro):
    return {
        "descripcion": "Servicio",
        "cantidad": Decimal("1"),
        "precio_unitario": Decimal("10.00"),
        "total_linea": Decimal("10.00"),
        "cuenta_contable_alegra": cuenta,
        "centro_costo_alegra": centro,
    }


def test_confirmed_history_excludes_unconfirmed_invoices_and_counts_one_row_each():
    nit = "900123456"
    _saved_invoice("HIST-PEND", nit, [_item("9999", "99")])
    _saved_invoice("HIST-FAIL", nit, [_item("9999", "99")], causacion_estado="fallido")
    for index in range(3):
        items = [_item("5105", "12")] * (index + 1)
        _saved_invoice(f"HIST-OK-{index}", nit, items, "exitoso", "procesado")

    rows = list_confirmed_provider_mappings(nit)

    assert len(rows) == 3
    for row in rows:
        assert {(m["cuenta"], m["centro_costo"]) for m in row["mappings"]} == {
            ("5105", "12")
        }
