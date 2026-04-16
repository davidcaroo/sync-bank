from typing import List, Optional
from pydantic import BaseModel, Field

class FacturaItemAI(BaseModel):
    descripcion: str = ""
    cantidad: float = 0.0
    precio_unitario: float = 0.0
    descuento: float = 0.0
    iva_porcentaje: float = 0.0
    total_linea: float = 0.0

class FacturaDIANAI(BaseModel):
    cufe: Optional[str] = None
    numero_factura: Optional[str] = None
    fecha_emision: Optional[str] = None
    fecha_vencimiento: Optional[str] = None
    nit_proveedor: Optional[str] = None
    nombre_proveedor: Optional[str] = None
    nit_receptor: Optional[str] = None
    subtotal: float = 0.0
    iva: float = 0.0
    rete_fuente: float = 0.0
    rete_ica: float = 0.0
    rete_iva: float = 0.0
    total: float = 0.0
    moneda: str = "COP"
    items: List[FacturaItemAI] = Field(default_factory=list)

class ExtraerPdfResponse(BaseModel):
    facturas: List[FacturaDIANAI] = Field(default_factory=list)
    confianza: float = 0.0
    warnings: List[str] = Field(default_factory=list)
    raw_text: Optional[str] = None
    pages: int = 0
    ocr_used: bool = False
