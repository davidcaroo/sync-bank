from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class FacturaItem(BaseModel):
    descripcion: str
    cantidad: float
    precio_unitario: float
    descuento: float = 0
    iva_porcentaje: float = 19
    total_linea: float
    cuenta_contable_alegra: Optional[str] = None
    centro_costo_alegra: Optional[str] = None

class FacturaDIAN(BaseModel):
    cufe: Optional[str] = None
    numero_factura: Optional[str] = None
    fecha_emision: Optional[datetime] = None
    fecha_vencimiento: Optional[datetime] = None
    nit_proveedor: Optional[str] = None
    nombre_proveedor: Optional[str] = None
    nit_receptor: Optional[str] = None
    subtotal: float = 0
    iva: float
    rete_fuente: float = 0
    rete_ica: float = 0
    rete_iva: float = 0
    total: float
    moneda: str = "COP"
    xml_raw: Optional[str] = None
    items: List[FacturaItem]
