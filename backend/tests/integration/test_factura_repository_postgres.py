from decimal import Decimal

import pytest

from repositories.factura_repository import find_factura_by_cufe, save_factura


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
        {"cufe": "CUFE-DUP-1", "numero_factura": "FE-2", "estado": "pendiente", "total": Decimal("10.00")},
        [],
    )
    second = save_factura(
        {"cufe": "CUFE-DUP-1", "numero_factura": "FE-3", "estado": "pendiente", "total": Decimal("20.00")},
        [],
    )

    assert second == {"factura_id": first["factura_id"], "duplicado": True}


def test_save_factura_rolls_back_when_an_item_is_invalid():
    with pytest.raises(Exception):
        save_factura(
            {"cufe": "CUFE-ROLLBACK-1", "numero_factura": "FE-4", "estado": "pendiente"},
            [{"descripcion": "Inválido", "cantidad": "no-es-numero"}],
        )

    assert find_factura_by_cufe("CUFE-ROLLBACK-1") is None
