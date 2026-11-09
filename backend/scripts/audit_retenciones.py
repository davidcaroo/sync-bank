"""Re-derive stored retentions/total from facturas.xml_raw and report differences.

Run from backend/:  python scripts/audit_retenciones.py [--nit 7474113] [--apply]
Read-only by default. --apply rewrites only the facturas columns; Alegra is never written.
"""

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.xml_parser import parse_xml_dian  # noqa: E402

FIELDS = ("rete_fuente", "rete_ica", "rete_iva", "total")


def find_mismatches(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        if not row.get("xml_raw"):
            continue
        try:
            parsed = parse_xml_dian(row["xml_raw"])
        except Exception:
            continue
        new = {f: round(float(getattr(parsed, f) or 0), 2) for f in FIELDS}
        old = {f: float(row.get(f) or 0) for f in FIELDS}
        if any(abs(new[f] - old[f]) > 0.01 for f in FIELDS):
            out.append({**row, "old": old, "new": new})
    return out


async def _alegra_bills(bill_ids: list[str]) -> dict:
    import httpx

    from services.alegra_client import AlegraClient

    alegra = AlegraClient()
    bills = {}
    async with httpx.AsyncClient(timeout=30) as client:
        for bill_id in bill_ids:
            bills[bill_id] = await alegra.get_bill_by_id(client, bill_id)
    return bills


def main() -> None:
    from repositories.database import connection, transaction
    from repositories.factura_repository import get_successful_causacion

    ap = argparse.ArgumentParser()
    ap.add_argument("--nit")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    sql = (
        "select id, numero_factura, nit_proveedor, estado, "
        "rete_fuente, rete_ica, rete_iva, total, xml_raw from facturas"
    )
    with connection() as conn:
        rows = conn.execute(
            sql + (" where nit_proveedor = %s" if args.nit else ""),
            (args.nit,) if args.nit else (),
        ).fetchall()

    mismatches = find_mismatches(rows)
    for m in mismatches:
        causacion = get_successful_causacion(str(m["id"]))
        m["bill_id"] = causacion and causacion.get("alegra_bill_id")
    bills = asyncio.run(
        _alegra_bills([m["bill_id"] for m in mismatches if m["bill_id"]])
    )

    print(f"{len(rows)} facturas revisadas, {len(mismatches)} con diferencias\n")
    for m in mismatches:
        print(f"{m['numero_factura']} | NIT {m['nit_proveedor']} | {m['estado']}")
        for f in FIELDS:
            if abs(m["new"][f] - m["old"][f]) > 0.01:
                print(f"    {f}: {m['old'][f]:,.2f} -> {m['new'][f]:,.2f}")
        bill = bills.get(m["bill_id"]) if m["bill_id"] else None
        if m["bill_id"]:
            if bill:
                print(
                    f"    Alegra bill {m['bill_id']}: total {bill.get('total')} "
                    f"balance {bill.get('balance')} retentions {bill.get('retentions')}"
                )
            else:
                print(f"    Alegra bill {m['bill_id']}: no encontrado")

    if args.apply and mismatches:
        with transaction() as conn:
            for m in mismatches:
                conn.execute(
                    "update facturas set rete_fuente = %s, rete_ica = %s, "
                    "rete_iva = %s, total = %s, updated_at = now() where id = %s",
                    (*(m["new"][f] for f in FIELDS), m["id"]),
                )
        print(f"\n{len(mismatches)} facturas actualizadas en la base de datos.")


if __name__ == "__main__":
    main()
