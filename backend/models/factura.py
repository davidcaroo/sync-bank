from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _to_float(value: object, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        raw = value.strip().replace(",", "")
        if not raw:
            return default
        try:
            return float(raw)
        except ValueError:
            return default
    return default

class FacturaItem(BaseModel):
    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    descripcion: str
    cantidad: float
    precio_unitario: float
    descuento: float = 0
    iva_porcentaje: float = 19
    total_linea: float
    cuenta_contable_alegra: Optional[str] = None
    centro_costo_alegra: Optional[str] = None

    @field_validator("descripcion", mode="before")
    @classmethod
    def _normalize_descripcion(cls, value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @field_validator("cantidad", "precio_unitario", "descuento", "iva_porcentaje", "total_linea", mode="before")
    @classmethod
    def _normalize_numbers(cls, value: object) -> float:
        return _to_float(value)

    @field_validator("cuenta_contable_alegra", "centro_costo_alegra", mode="before")
    @classmethod
    def _normalize_optional_text(cls, value: object) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def normalize(self) -> "FacturaItem":
        calculated_line_total = max((self.cantidad * self.precio_unitario) - self.descuento, 0.0)
        line_total = self.total_linea if self.total_linea > 0 else calculated_line_total
        return self.model_copy(
            update={
                "descripcion": self.descripcion.strip() or "Articulo sin descripcion",
                "cantidad": max(self.cantidad, 0.0),
                "precio_unitario": max(self.precio_unitario, 0.0),
                "descuento": max(self.descuento, 0.0),
                "iva_porcentaje": max(self.iva_porcentaje, 0.0),
                "total_linea": line_total,
            }
        )

class FacturaDIAN(BaseModel):
    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    cufe: Optional[str] = None
    numero_factura: Optional[str] = None
    fecha_emision: Optional[datetime] = None
    fecha_vencimiento: Optional[datetime] = None
    nit_proveedor: Optional[str] = None
    nombre_proveedor: Optional[str] = None
    nit_receptor: Optional[str] = None
    subtotal: float = 0
    iva: float = 0
    rete_fuente: float = 0
    rete_ica: float = 0
    rete_iva: float = 0
    total: float = 0
    moneda: str = "COP"
    xml_raw: Optional[str] = None
    items: list[FacturaItem] = Field(default_factory=list)

    @field_validator(
        "subtotal",
        "iva",
        "rete_fuente",
        "rete_ica",
        "rete_iva",
        "total",
        mode="before",
    )
    @classmethod
    def _normalize_monetary_values(cls, value: object) -> float:
        return _to_float(value)

    @field_validator("cufe", "numero_factura", "nit_proveedor", "nombre_proveedor", "nit_receptor", "moneda", mode="before")
    @classmethod
    def _normalize_text_values(cls, value: object) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def normalize(self) -> "FacturaDIAN":
        normalized_items = [item.normalize() for item in self.items]
        subtotal = self.subtotal if self.subtotal > 0 else sum(item.total_linea for item in normalized_items)
        total_retentions = max(self.rete_fuente, 0.0) + max(self.rete_ica, 0.0) + max(self.rete_iva, 0.0)
        gross_total = subtotal + max(self.iva, 0.0)
        total = self.total if self.total > 0 else max(gross_total - total_retentions, 0.0)

        return self.model_copy(
            update={
                "cufe": self.cufe or "SIN-CUFE",
                "numero_factura": self.numero_factura or "SIN-NUMERO",
                "nit_proveedor": self.nit_proveedor or "999999999",
                "nombre_proveedor": self.nombre_proveedor or "Proveedor Generico",
                "nit_receptor": self.nit_receptor or "123456789",
                "moneda": self.moneda or "COP",
                "subtotal": subtotal,
                "iva": max(self.iva, 0.0),
                "rete_fuente": max(self.rete_fuente, 0.0),
                "rete_ica": max(self.rete_ica, 0.0),
                "rete_iva": max(self.rete_iva, 0.0),
                "total": total,
                "items": normalized_items,
            }
        )
