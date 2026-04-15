from models.factura import FacturaDIAN, FacturaItem


def test_factura_item_normalize_calculates_total_when_missing():
    item = FacturaItem(
        descripcion="  Servicio QA  ",
        cantidad="2",
        precio_unitario="1000",
        descuento="100",
        iva_porcentaje="19",
        total_linea=0,
    )

    normalized = item.normalize()

    assert normalized.descripcion == "Servicio QA"
    assert normalized.cantidad == 2.0
    assert normalized.precio_unitario == 1000.0
    assert normalized.total_linea == 1900.0


def test_factura_normalize_sets_defaults_and_totals():
    factura = FacturaDIAN(
        cufe="",
        numero_factura=None,
        nit_proveedor="",
        nombre_proveedor="",
        nit_receptor=None,
        subtotal=0,
        iva=190,
        rete_fuente=10,
        rete_ica=5,
        rete_iva=0,
        total=0,
        items=[
            FacturaItem(
                descripcion=" Item 1 ",
                cantidad=1,
                precio_unitario=1000,
                descuento=0,
                iva_porcentaje=19,
                total_linea=1000,
            )
        ],
    )

    normalized = factura.normalize()

    assert normalized.cufe == "SIN-CUFE"
    assert normalized.numero_factura == "SIN-NUMERO"
    assert normalized.nit_proveedor == "999999999"
    assert normalized.nombre_proveedor == "Proveedor Generico"
    assert normalized.nit_receptor == "123456789"
    assert normalized.subtotal == 1000.0
    assert normalized.total == 1175.0
    assert normalized.items[0].descripcion == "Item 1"
