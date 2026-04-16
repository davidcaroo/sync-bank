import asyncio
import json
import logging
from typing import Tuple

import ollama

from llm_utils import extract_json_object
from pdf_models import FacturaDIANAI

logger = logging.getLogger("ai-service.pdf_mapper")

PROMPT_TEMPLATE = """
Eres un contador colombiano experto en facturas DIAN. Extrae una estructura JSON limpia desde el texto.

Texto de la factura:
{raw_text}

Responde SOLO con JSON y esta estructura exacta:
{{
  "facturas": [
    {{
      "cufe": "...",
      "numero_factura": "...",
      "fecha_emision": "YYYY-MM-DD",
      "fecha_vencimiento": "YYYY-MM-DD",
      "nit_proveedor": "...",
      "nombre_proveedor": "...",
      "nit_receptor": "...",
      "subtotal": 0,
      "iva": 0,
      "rete_fuente": 0,
      "rete_ica": 0,
      "rete_iva": 0,
      "total": 0,
      "moneda": "COP",
      "items": [
        {{
          "descripcion": "...",
          "cantidad": 0,
          "precio_unitario": 0,
          "descuento": 0,
          "iva_porcentaje": 0,
          "total_linea": 0
        }}
      ]
    }}
  ],
  "confianza": 0.0,
  "warnings": ["..."]
}}
"""

async def map_text_to_facturas(
    raw_text: str,
    *,
    model: str,
    timeout_seconds: float,
    max_chars: int,
    retry_timeout_seconds: float | None = None,
    retry_max_chars: int | None = None,
) -> Tuple[list[FacturaDIANAI], float, list[str]]:
    trimmed = (raw_text or "").strip()
    if max_chars > 0:
        trimmed = trimmed[:max_chars]

    async def _call_ollama(prompt_text: str, timeout_value: float):
        return await asyncio.wait_for(
            asyncio.to_thread(
                ollama.chat,
                model=model,
                messages=[
                    {"role": "system", "content": "Responde siempre en JSON valido."},
                    {"role": "user", "content": prompt_text},
                ],
            ),
            timeout=timeout_value,
        )

    prompt = PROMPT_TEMPLATE.format(raw_text=trimmed)

    try:
        response = await _call_ollama(prompt, timeout_seconds)
    except TimeoutError:
        retry_text = trimmed
        if retry_max_chars and retry_max_chars > 0:
            retry_text = trimmed[:retry_max_chars]
        retry_prompt = PROMPT_TEMPLATE.format(raw_text=retry_text)
        try:
            response = await _call_ollama(retry_prompt, retry_timeout_seconds or timeout_seconds)
        except TimeoutError:
            return [], 0.0, ["timeout_ollama"]
        except Exception as exc:
            logger.exception("ollama_error", extra={"error": str(exc)})
            return [], 0.0, ["ollama_error"]
    except Exception as exc:
        logger.exception("ollama_error", extra={"error": str(exc)})
        return [], 0.0, ["ollama_error"]

    content = response.get("message", {}).get("content", "")
    try:
        parsed = extract_json_object(content)
    except Exception as exc:
        logger.warning("invalid_llm_json", extra={"error": str(exc)})
        return [], 0.0, ["invalid_llm_json"]

    facturas_raw = parsed.get("facturas") or []
    facturas: list[FacturaDIANAI] = []
    for item in facturas_raw:
        try:
            facturas.append(FacturaDIANAI.model_validate(item))
        except Exception:
            continue

    try:
        confianza = float(parsed.get("confianza", 0.0))
    except Exception:
        confianza = 0.0

    warnings = parsed.get("warnings") or []
    if not isinstance(warnings, list):
        warnings = [str(warnings)]

    return facturas, max(0.0, min(confianza, 1.0)), [str(w) for w in warnings]
