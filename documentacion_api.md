**Documentación de la API — Sync-bank**

**Resumen**
- **Descripción**: API HTTP del backend Sync-bank; gestiona ingestión y causación de facturas DIAN y operaciones relacionadas.
- **Base URL**: `http://localhost:8000/api`
- **Raíz**: `GET /` devuelve un saludo y versión mínima (ver [backend/main.py](backend/main.py#L1-L120)).

**Autenticación y cabeceras**
- **X-Admin-Key**: header requerido por algunos endpoints administrativos (ver `POST /api/providers/recompute`). Configurable vía `ADMIN_API_KEY` en el fichero de entorno.
- **X-Request-Id**: opcional; si se envía, se devuelve en la respuesta. Si no, el servidor genera uno y lo expone en la cabecera.

**Formato de errores global**
- **Unhandled (500)**: el manejador global devuelve:

```
{
  "message": "Error interno del servidor",
  "code": "INTERNAL_ERROR",
  "request_id": "..."
}
```

- Los endpoints también usan `HTTPException` con `status_code` y `detail` (puede ser string o un objeto con más campos).

**Tipos de error/Excepciones relevantes**
- **ServiceError** / **RemoteAPIError**: errores de servicio y de APIs externas (internos).
- **InvalidXMLError**: XML inválido o no parseable.
- **AlegraDuplicateBillError**: Alegra indica documento duplicado — mapeado a `409` con código `DUPLICADO_ALEGRA`.
- Implementación en [backend/services/errors.py](backend/services/errors.py#L1-L80).

**Endpoints**

**Facturas** ([backend/routers/facturas.py](backend/routers/facturas.py#L1-L200))
- **POST /api/facturas/preview-upload**: Previsualiza archivos subidos (XML o ZIP). Multipart `files` (lista). Query param: `apply_ai` (default `true`).
  - Request: `multipart/form-data` con múltiples `files`.
  - Response: `{"summary": {...}, "files": [result,...]}` donde cada `result` contiene:
    - **file_name**, **entry_name**, **status**: `valid|invalid|duplicate` (preview) y opcional `reason`.
    - Para `valid` incluye `factura_preview` con campos: `cufe`, `numero_factura`, `fecha_emision`, `nit_proveedor`, `nombre_proveedor`, `items` (cada item con `descripcion`, `cantidad`, `precio_unitario`, `total_linea`, `cuenta_contable_alegra`, `centro_costo_alegra`, `prefill_source`, `confidence`).

- **POST /api/facturas/upload**: Igual que `preview-upload` pero persiste en la base de datos.
  - Summary en la respuesta incluye `created`, `duplicates`, `errors`.
  - `apply_ai` controla si se solicita clasificación automática de cuentas.

- **GET /api/facturas/stats**: Estadísticas rápidas: `{"hoy":int, "causadas":int, "pendientes":int, "errores":int}`.

- **GET /api/facturas**: Listado paginado.
  - Query params: `page` (default 1), `page_size` (default 20), `estado`, `proveedor`, `desde`, `hasta` (filtros por fecha/estado/proveedor).
  - Response: `{"data":[factura], "count":int, "page":int, "page_size":int}`.
  - El objeto `factura` contiene campos como `cufe`, `numero_factura`, `fecha_emision`, `nit_proveedor`, `nombre_proveedor`, `subtotal`, `iva`, `total`, `items` (items con `prefill_source` y `confidence`). Ver el modelo en [backend/models/factura.py](backend/models/factura.py#L1-L140).

- **GET /api/facturas/{factura_id}**: Devuelve una factura con sus items y metadatos de prefill.

- **POST /api/facturas/{factura_id}/causar**: Intenta causar la factura en Alegra.
  - Request body (JSON): `{"item_overrides": [{"item_id": "...", "cuenta_contable_alegra": "...", "centro_costo_alegra": "..."}, ...]}`. Tipado por `CausarFacturaRequest`.
  - Respuestas:
    - `200` (OK): devuelve la respuesta cruda de Alegra (la factura creada en Alegra) en caso de éxito.
    - `404`: factura no encontrada.
    - `409`: conflicto — puede devolver objetos con estructura:
      - `{"message":"Factura ya causada","code":"FACTURA_YA_CAUSADA","alegra_bill_id": <id>}`
      - `{"message":"Factura en revision manual...","code":"REQUIERE_CONFIRMACION_MANUAL","missing_item_ids":[...]}`
      - `{"message":...,"code":"DUPLICADO_ALEGRA"}` si Alegra reporta duplicado.
    - `502`: error al comunicarse con Alegra u otro servicio remoto.

**Contactos** ([backend/routers/contactos.py](backend/routers/contactos.py#L1-L200))
- **GET /api/contactos/**: Listado y búsqueda de contactos.
  - Query params: `tipo` (`all|provider|client`), `estado`, `search`, `page`, `page_size`.
  - Behavior: búsqueda por texto y por identificación (si el término es numérico realiza una consulta directa a Alegra para asegurar coincidencias).
  - Response: `{"data": [contactos], "count": int, "page": int, "page_size": int, "has_more": bool}`.

- **GET /api/contactos/{contact_id}**: Obtiene contacto por id.
- **POST /api/contactos/**: Crea contacto. Payload ejemplo (JSON):

```
{
  "name": "Proveedor S.A.",
  "identification": "123456789-0",
  "identification_type": "NIT",
  "email": "proveedor@correo.com",
  "contact_type": ["provider"]
}
```

- **PATCH /api/contactos/{contact_id}**: Actualiza campos permitidos.
- **DELETE /api/contactos/{contact_id}**: Elimina contacto (respuesta: `{"status":"deleted","id": "..."}`).

Campos normalizados devueltos por los endpoints de contactos incluyen: `id`, `name`, `identification`, `identification_type`, `dv`, `kind_of_person`, `regime`, `department`, `city`, `address`, `country`, `email`, `phone_primary`, `mobile`, `status`, `type`.

**Configuración / Catálogos (Alegra)** ([backend/routers/config.py](backend/routers/config.py#L1-L200))
- **GET /api/config/alegra/catalogo?refresh=false**: Devuelve listas `categories` y `cost_centers` desde Alegra. `refresh=true` fuerza recarga.
- **GET /api/config/alegra/proveedor/resolve?nit=...&nombre=...**: Resuelve `provider_id` en Alegra para un NIT/nombre dado.
- **GET /api/config/**: Lista registros de mapeo de cuentas.
- **POST /api/config/**: Crea un mapeo (payload libre tipo `dict`).
- **PATCH /api/config/{config_id}**: Actualiza mapeo.
- **DELETE /api/config/{config_id}**: Elimina mapeo.

**Providers (mantenimiento)** ([backend/routers/providers.py](backend/routers/providers.py#L1-L160))
- **POST /api/providers/recompute**: Reconstruye mapeo de proveedor a cuenta contable.
  - Query param opcional: `nit` (si se pasa, sólo se reprocesa ese proveedor).
  - Requiere header `X-Admin-Key` (ver [backend/security/admin_auth.py](backend/security/admin_auth.py#L1-L80)).

**Logs** ([backend/routers/logs.py](backend/routers/logs.py#L1-L140))
- **GET /api/logs/**: Lista paginada de logs guardados.
  - Query params: `page`, `page_size`, `estado`.
  - Response: `{"data": [...], "count": int, "page": int, "page_size": int}`.

**Proceso (ejecución manual / estado)** ([backend/routers/proceso.py](backend/routers/proceso.py#L1-L160))
- **POST /api/proceso/manual**: Ejecuta manualmente el job que revisa emails y procesa facturas; respuesta con `status`, `timestamp` y `summary` (`created`, `duplicates`, `invalid`, `errors`).
- **GET /api/proceso/status**: Estado de la última ejecución (timestamp + resumen).

**Modelos importantes**
- `FacturaDIAN` / `FacturaItem`: ver [backend/models/factura.py](backend/models/factura.py#L1-L140) para definición de campos usados al crear la factura en Alegra.
- `ContactPayload`: definición en [backend/routers/contactos.py](backend/routers/contactos.py#L1-L80).

**Ejemplos rápidos (curl)**
- Subir archivos (preview):

```
curl -X POST "http://localhost:8000/api/facturas/preview-upload?apply_ai=true" \
  -F "files=@/path/to/a.xml" -F "files=@/path/to/b.zip"
```

- Causar factura (con overrides):

```
curl -X POST "http://localhost:8000/api/facturas/1234/causar" \
  -H "Content-Type: application/json" \
  -d '{"item_overrides":[{"item_id":"1","cuenta_contable_alegra":"5001"}] }'
```

- Reconstruir mapping (admin):

```
curl -X POST "http://localhost:8000/api/providers/recompute" -H "X-Admin-Key: tu_clave_admin"
```

**Ejecutar localmente**
- Formas recomendadas:
  - `make dev` (levanta `docker-compose` y todos los servicios) — ver `README.md` en la raíz.
  - Para desarrollo directo de la API: `uvicorn backend.main:app --reload --port 8000` y establecer variables en `.env` (plantilla en `.env.example`).
- Variables mínimas en `.env`: `SUPABASE_URL`, `SUPABASE_KEY`, `ALEGRA_EMAIL`, `ALEGRA_TOKEN`, `IMAP_USER`, `IMAP_PASS`. Ver [.env.example](.env.example#L1-L80).

**Notas operativas y recomendaciones**
- `apply_ai` en endpoints de ingestión controla si se consulta el servicio AI para sugerir cuentas contables (umbral controlado por `AI_CONFIDENCE_THRESHOLD`).
- Los procesos que contactan a Alegra usan timeouts y pueden devolver `502` cuando la API externa falla.
- Para endpoints administrativos asegúrate de configurar `ADMIN_API_KEY` en el entorno.
- El `X-Request-Id` facilita trazabilidad en logs (el middleware lo agrega y lo devuelve en la respuesta).

**Archivos relevantes**
- [backend/main.py](backend/main.py#L1-L200)
- [backend/routers/facturas.py](backend/routers/facturas.py#L1-L200)
- [backend/routers/contactos.py](backend/routers/contactos.py#L1-L400)
- [backend/routers/config.py](backend/routers/config.py#L1-L200)
- [backend/routers/providers.py](backend/routers/providers.py#L1-L200)
- [backend/routers/logs.py](backend/routers/logs.py#L1-L120)
- [backend/routers/proceso.py](backend/routers/proceso.py#L1-L160)
- [backend/services/factura_service.py](backend/services/factura_service.py#L1-L800)
- [backend/services/ingestion/processor.py](backend/services/ingestion/processor.py#L1-L240)
- [backend/services/errors.py](backend/services/errors.py#L1-L80)
- [backend/models/factura.py](backend/models/factura.py#L1-L140)

---
Documentación generada automáticamente para ayudar al equipo de desarrollo. 

**Ejemplos Postman**

- **Importar y configurar**:
  - En Postman: Import → Raw text o File. Para pruebas locales, crea un Environment con variables:
    - `base_url` = `http://localhost:8000`
    - `admin_key` = `<tu_admin_key>`
    - `apply_ai` = `true`

- **1) Previsualizar subida (multipart/form-data)**:
  - Método: POST
  - URL: {{base_url}}/api/facturas/preview-upload?apply_ai={{apply_ai}}
  - Body → form-data: agrega una o varias keys `files` (tipo File) y selecciona los XML/ZIP.
  - Headers: Postman gestiona `Content-Type` automáticamente al usar `form-data`.
  - Respuesta esperada (extracto):

    {
      "summary": {"total_files":1, ...},
      "files": [{"file_name":"a.xml","status":"valid","factura_preview":{...}}]
    }

- **2) Subir y persistir (upload)**:
  - Método: POST
  - URL: {{base_url}}/api/facturas/upload?apply_ai={{apply_ai}}
  - Body → form-data con `files` (archivos).
  - Respuesta: `summary` con `created`, `duplicates`, `errors`.

- **3) Causar factura (JSON)**:
  - Método: POST
  - URL: {{base_url}}/api/facturas/:factura_id/causar (reemplaza :factura_id).
  - Headers: Content-Type: application/json
  - Body (raw JSON):

    {
      "item_overrides": [
        {"item_id": "1", "cuenta_contable_alegra": "5001", "centro_costo_alegra": null}
      ]
    }
  - Respuestas:
    - 200 → objeto con la respuesta de Alegra (factura creada)
    - 409 → conflicto (factura ya causada o requiere confirmación manual)

- **4) Reconstruir mapping (Admin)**:
  - Método: POST
  - URL: {{base_url}}/api/providers/recompute?nit=900123456
  - Headers: X-Admin-Key: {{admin_key}}
  - Respuesta: resumen con `ok`, `count`, `results`.

- **5) Consultas GET (ej. facturas, contactos)**:
  - GET {{base_url}}/api/facturas?page=1&page_size=20&estado=pendiente
  - GET {{base_url}}/api/contactos?search=ACME&tipo=provider
  - No requieren body; si el endpoint necesita autenticación admin, añade X-Admin-Key.

**Consejos Postman**
- Para subir múltiples archivos en Postman añade varias entradas `files` de tipo `File` en la pestaña `form-data`.
- Usa `{{base_url}}` en las URLs del Collection para cambiar fácilmente entre local y producción.

**Actualizaciones recientes (2026-04-14)**
- **Recausación segura**: ahora `POST /api/facturas/{factura_id}/causar` permite recausar cuando la factura fue eliminada en Alegra y valida primero por `alegra_bill_id` para evitar esperas largas.
- **Selección de IVA mejorada**:
  - El sistema toma el porcentaje real del XML (`iva_porcentaje`).
  - Evita `IVA generado` para causación de compras.
  - Prioriza `IVA desc 19% por compras` o `IVA desc 19% por servicios` según política por NIT/proveedor (`backend/services/provider_tax_policy.py`) y contexto del ítem.
  - Para IVA 5%, selecciona el impuesto activo de 5% cuando está configurado en Alegra.
- **Centro de costo robusto**: se corrige envío de `costCenter` cuando el valor viene como texto compuesto (ej. `11 | ADMINISTRATIVO`), extrayendo correctamente el ID numérico.