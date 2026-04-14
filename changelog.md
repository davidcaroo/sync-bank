# Changelog

## [2026-04-14] - Fix: Causación con IVA en Alegra
### Corregido
- Se eliminó el impuesto fijo `tax: [{"id": 1}]` en `backend/services/alegra_client.py` al crear bills.
- Ahora el backend resuelve el `tax.id` dinámicamente por porcentaje de IVA de cada ítem (`iva_porcentaje`) consultando `GET /taxes` en Alegra.
- Si no existe un impuesto activo en Alegra para el porcentaje requerido (ej. 19%), el sistema ya no causa con impuesto incorrecto; devuelve error explícito para corregir configuración.

### Hallazgo técnico
- La factura sí llegaba con IVA desde DIAN y con `iva_porcentaje=19` por ítem.
- El IVA se perdía en la causación porque `id=1` en la cuenta Alegra corresponde a IVA `0%`.

### Mejorado
- Se añadió notificación en frontend (`frontend/src/pages/Facturas.jsx`) para informar al usuario cuando falta configuración de impuesto IVA en Alegra.

### Validación
- Verificación de datos de factura en backend: `iva_total=9531.932772` e ítems con `iva_porcentaje=19.0`.
- Verificación de impuestos en Alegra: disponible `19%` y resolución dinámica activa (`resolved_tax_id_19 = 4`).
- Pruebas backend: `12 passed`.


## [2026-04-14] - Fix: error 502 en causación y notificación al usuario
### Corregido
- **Causación en Alegra (`POST /api/facturas/{id}/causar`)**: se ajustó la resolución de proveedor en `backend/services/alegra_client.py` para manejar correctamente el caso en que Alegra responde "ya existe un contacto con la identificación".
- El flujo ahora intenta recuperar el contacto existente por:
	- búsqueda por identificación con `type=provider`,
	- fallback por identificación sin filtrar `type`,
	- y fallback por `contactId` retornado por Alegra en el error (`code=2006`).

### Mejorado
- **Notificación de frontend** en `frontend/src/pages/Facturas.jsx`: cuando ocurre `502` durante `Causar en Alegra`, se muestra un mensaje explicativo y accionable para el usuario (no solo error genérico).

### Validación
- Reproducción del caso reportado con factura `f313c2fa-2022-4020-b7c3-67f286a9d19a`:
	- Antes: `502 Bad Gateway`.
	- Después de la corrección: `200 OK` con creación de bill en Alegra.
- Suite backend en contenedor: `10 passed`.


## [2026-04-14] - Deploy: Docker images built and stack tested
### Acciones realizadas
- Construidas imágenes y levantado el stack usando `docker compose build` y `docker compose up -d`.
- Imágenes locales creadas: `sync-bank-backend:latest`, `sync-bank-frontend:latest`, `sync-bank-ai-service:latest`.
- Ejecutada la suite de pruebas dentro de un contenedor temporal con instalación rápida de deps de test:

```
docker compose run --rm backend /bin/sh -c "pip install pytest pytest-asyncio -q; python -m pytest -q"
```

- Resultado de tests: `9 passed, 3 warnings`.

### Notas
- Los tests se ejecutaron instalando `pytest` en un contenedor temporal; se recomienda añadir las dependencias de desarrollo a `backend/requirements-dev.txt` o incluirlos en la imagen de CI para evitar instalaciones ad-hoc en runtime.
- No se realizó push a un registry remoto. Si deseas que suba las imágenes a Docker Hub u otro registry, indícame el nombre del repositorio y credenciales, o proporciona acceso mediante `docker login` en tu entorno.

## [2026-04-14] - Refactor: Cliente Alegra, excepciones tipadas y factura_service
### Añadido / Modificado
- **Excepciones tipadas**: `backend/services/errors.py` — `ServiceError`, `RemoteAPIError`, `InvalidXMLError`, `AlegraDuplicateBillError`. Objetivo: centralizar tipos de error para manejo consistente y facilitar testeo.
- **Alegra HTTP client**: `backend/services/alegra_client.py` — nuevo cliente HTTP con helpers para llamadas a Alegra (catálogos, contactos, creación de bills y parsing). Ventaja: desacopla lógica HTTP/parsing de la capa de negocio y facilita mocks en pruebas.
- **Facade `alegra_service`**: `backend/services/alegra_service.py` refactorizado a una fachada delgada que delega en `AlegraClient`, preservando la API pública existente para compatibilidad.
- **Servicio de facturas**: `backend/services/factura_service.py` — migrada la lógica principal del router (`hidratación` de items, enriquecimiento monetario, preview/upload y flujo de `causar`) a un servicio testable y reutilizable.
- **Routers**: `backend/routers/facturas.py` convertido en una capa de presentación ligera que delega en `FacturaService`, reduciendo la responsabilidad de la capa HTTP.
- **Validación y compilación**: se ejecutó verificación de sintaxis (`python -m compileall services routers`) y los módulos compilados sin errores.
- **Estado de tests**: intento de ejecución de la suite falló en el entorno actual porque `pytest` no está instalado; por eso las pruebas unitarias quedan pendientes de integrar en CI/local.

### Motivo y ventajas
- Separación de responsabilidades: HTTP, lógica de negocio y manejo de errores ahora están desacoplados.
- Mejor cobertura en pruebas: `AlegraClient` y `FacturaService` pueden testearse por separado con mocks controlados.
- Menor riesgo al desplegar: el refactor es no disruptivo — las firmas públicas de `alegra_service` y las rutas se mantienen.
- Reutilización y mantenimiento: `AlegraClient` sirve como punto único para mejoras (caching, retries, logging) sin tocar la lógica de negocio.

### Pendiente / Próximos pasos
- Descomponer `backend/services/ingestion_service.py` en tres módulos:
	- `backend/services/ingestion/extractor.py`: extracción y decodificación de ZIP/XML, detección de encoding y soporte para ZIP anidados.
	- `backend/services/ingestion/processor.py`: orquestación del procesamiento, persistencia vía repositorios y manejo de errores/retry.
	- `backend/services/ingestion/prefill.py`: lógica de prefill (IA, mapeos por NIT, llamadas a `AlegraClient`).
	- Mantener un facade `backend/services/ingestion_service.py` que preserve la interfaz externa.
- Añadir pruebas unitarias:
	- `AlegraClient` (mock de `httpx`), `FacturaService` (mock de `AlegraClient` y repositorios) y helpers de extracción ZIP/XML.
- Ajustar CI/Docker para instalar `pytest` y ejecutar la suite en pipeline.
- Modularizar `backend/services/xml_parser.py` hacia una interfaz `DIANParser` reutilizable.
- Considerar mejoras operativas (cache compartida tipo Redis, mover IMAP/IO bloqueante a workers/asíncrono).

### Estado
- Implementado: excepciones tipadas, `AlegraClient`, fachada `alegra_service`, `FacturaService`, y router `facturas` delgado.
- Validado: compilación de módulos sin errores.
- Pendiente: pruebas unitarias (bloqueadas por entorno), descomposición de `ingestion_service.py`, modularización de `xml_parser.py`.

## [2026-04-14] - Cierre de Fase: descomposición de ingestion, parser DIAN modular y pruebas
### Añadido / Modificado
- **Descomposición de ingesta en 3 módulos**:
	- `backend/services/ingestion/extractor.py`: extracción XML desde adjuntos y ZIP (incluye ZIP anidados y detección de codificación).
	- `backend/services/ingestion/processor.py`: orquestación de parseo, prefill (config/IA), control de duplicados y persistencia.
	- `backend/services/ingestion/prefill.py`: construcción de contexto de clasificación (categorías y centros de costo).
	- `backend/services/ingestion/__init__.py`: exports del paquete.

- **Facade compatible mantenido**:
	- `backend/services/ingestion_service.py` conserva la API pública (`IngestionService`, `XMLDocument`, `ingestion_service`) y delega internamente en los módulos nuevos.
	- Se preservó compatibilidad con imports existentes de routers/servicios y con monkeypatches de tests.

- **Parser DIAN modularizado**:
	- `backend/services/xml_parser.py` pasó de una función monolítica a `DIANParser` con métodos separados para:
		- unwrap de `AttachedDocument`
		- extracción de metadatos (NIT/nombre)
		- extracción de totales e impuestos
		- extracción y clasificación de retenciones
		- cálculo de total neto pagadero
		- extracción de items
	- Se mantiene `parse_xml_dian(...)` como wrapper/facade compatible para no romper consumo actual.

- **Pruebas unitarias nuevas**:
	- `backend/tests/test_alegra_client.py`
	- `backend/tests/test_factura_service.py`
	- `backend/tests/test_xml_parser.py`

### Validación
- **Suite backend**: `python -m pytest -q` ejecutada exitosamente.
	- Resultado: `9 passed`.
- **Compilación**: `python -m compileall services routers tests` sin errores.

### Hallazgos de entorno (Windows + Python 3.14)
- Se detectó incompatibilidad al instalar `requirements.txt` con pins antiguos (`lxml==5.1.0` y stack de `pydantic==2.6.1`/`pydantic-core`) en Python 3.14.
- Para validación local se usaron dependencias compatibles con 3.14 (`lxml>=6`, `fastapi`/`supabase`/`httpx` actuales, `pydantic-settings`).

### Ventajas operativas
- Menor acoplamiento y mayor mantenibilidad en ingesta.
- Mejor testabilidad por separación extractor/processor/prefill.
- Menor riesgo de regresión al mantener facade e interfaz pública.
- Base lista para evolución (retries, observabilidad, paralelización) sin tocar capa HTTP.

### Pendiente recomendado
- Alinear `backend/requirements.txt` con versiones compatibles para Python 3.14 (o fijar versión de runtime soportada) para evitar fallos de instalación en nuevos entornos.

## [2026-04-13] - Correccion CORS y respuestas consistentes
### Corregido
- **CORS en API**: Se reordeno el middleware para garantizar `Access-Control-Allow-Origin` en todas las respuestas, evitando bloqueos desde `http://localhost:3000`.

## [2026-04-09] - Estabilidad Operativa: ZIP, Zona Horaria, Duplicados Alegra e Iconos
### Corregido
- **Sincronización y carga ZIP robusta**:
	- Se unificó la extracción XML para carga manual y correo con una sola lógica compartida.
	- Soporte para ZIP anidados y decodificaciones adicionales (`utf-8-sig`, `utf-16`, `latin-1`).
	- Cuando un ZIP no contiene XML procesables, ahora se registra y reporta explícitamente en lugar de quedar silencioso.

- **Diagnóstico visible de inválidas**:
	- El proceso manual de sincronización ahora retorna resumen estructurado (`created`, `duplicates`, `invalid`, `errors`) y detalle de inválidas por archivo/entrada/causa.
	- Se añadió en Dashboard una sección de resultado de última sincronización con tabla de inválidos para auditoría inmediata.

- **Zona horaria fija a Colombia (`America/Bogota`)**:
	- Se estandarizó el cálculo de fecha/hora del backend con helper centralizado de zona horaria.
	- El KPI de "Facturas Hoy" ahora usa fecha local de Bogotá.
	- Se ajustó `docker-compose.yml` para ejecutar servicios con `TZ=America/Bogota`.
	- En frontend, el formateo de fechas sensibles se fijó a `America/Bogota`.

- **Facturas duplicadas: enriquecimiento desde Alegra**:
	- Al consultar detalle de facturas en estado `duplicado`/`procesado`, el backend intenta hidratar cuenta y centro de costo desde la bill existente en Alegra.
	- Se persisten esos campos en `items_factura` cuando están vacíos localmente.
	- En el modal de factura, si la cuenta/centro existe pero no aparece en catálogo local, se muestra igualmente como valor "registrado en Alegra" para evitar campos visualmente vacíos.

- **Estabilidad en migración de iconos SVG**:
	- Se agregaron exports faltantes en la librería de iconos (`IconHistory`, `IconMoonStar`, `IconUserCheck`, `IconUserMinus`) para resolver errores de importación en runtime/build.

### Validación
- Build de frontend completado exitosamente con Vite tras los ajustes de iconos.
- Despliegue actualizado con `docker compose up -d --build` sobre todo el stack.
 
## [2026-04-09] - Modernización UI: Iconografía SVG y Eliminación de Emojis
### Contexto
- Se identificó una inconsistencia visual por el uso de emojis decorativos y múltiples librerías de iconos (`lucide-react`) mezcladas en la interfaz administrativa.
- Objetivo: Unificar la línea visual bajo el estándar de **SB Admin 2** usando únicamente componentes SVG inline controlados.

### Añadido
- **Sistema Unificado de Iconos** (`frontend/src/components/icons/Icons.jsx`):
	- Creación de una librería de componentes SVG profesionales (`IconSearch`, `IconFilter`, `IconPlus`, `IconRefresh`, `IconHistory`, etc.).
	- Estándar visual: Grosor de trazo `1.8`, sin relleno, color dinámico via `currentColor`.
- **Nuevos estados visuales**:
	- Rediseño de estados de carga (`IconLoading`) con animación `spin` integrada.
	- Rediseño de estados vacíos (`IconArchive`, `IconInbox`) con opacidad controlada.

### Corregido
- **Eliminación global de emojis**: Se eliminaron todos los emojis (`⏳`, `📂`, `📄`, `✕`, `📋`, `📭`, `↻`, `🗂️`) del código fuente JSX.
- **Estandarización de componentes**:
	- **Facturas**: Reemplazados emojis en carga de archivos, zona Drag & Drop y tablas.
	- **Auditoría (Logs)**: Reemplazadas flechas de texto (`←`, `→`) por iconos SVG de navegación.
	- **Dashboard**: Reemplazada iconografía de KPI y estados vacíos.
	- **Configuración**: Unificación de iconos en botones de edición, guardado y eliminación.
- **Limpieza de dependencias**: Migración paulatina de `lucide-react` hacia el sistema interno de iconos para reducir la carga de librerías externas.

### Mejorado
- **Contactos (Directorio)**: 
	- Rediseño de las **Cards KPI** (Total, Activos, Inactivos) para alinearlas estrictamente al layout de SB Admin 2 (borde lateral de color, fondo blanco, sombra sutil y altura compacta).
	- Iconografía de alta resolución en el resumen de contactos.
- **Sidebar y Topbar**: Actualización de todos los iconos de navegación y controles de usuario a la nueva línea visual SVG.


## [2026-04-09] - Exactitud Monetaria de Facturas DIAN y Corrección de Total Real
### Contexto
- Se detectó una diferencia operativa entre el valor mostrado en el sistema y el valor real pagadero del documento en proveedores con retenciones.
- Caso de referencia validado: factura `ALTX17971` (ALMARTEX ASOCIADOS S.A.S.), donde el sistema mostraba el bruto y el soporte requería reflejar el neto pagadero.

### Corregido
- **Cálculo del total real pagadero**: se robusteció el parser DIAN para evitar mostrar como total final un valor bruto cuando el XML reporta retenciones en bloques separados.
- **Consistencia visual en toda la app**: se dejó de mostrar el total bruto como principal en Dashboard y Facturas; ahora se prioriza el total neto pagadero.
- **Recuperación de exactitud en registros históricos**: al consultar facturas, el backend recalcula campos monetarios desde `xml_raw` cuando está disponible, para corregir visualización sin esperar reprocesamiento masivo inicial.

### Añadido
- **Parser monetario robusto en XML** (`backend/services/xml_parser.py`):
	- Normalizador numérico seguro para conversiones (`_to_float`).
	- Lectura de montos UBL relevantes:
		- `LineExtensionAmount` (subtotal)
		- `TaxInclusiveAmount` (bruto con impuestos)
		- `PayableAmount` (pagadero)
		- `AllowanceTotalAmount` (descuentos globales)
		- `ChargeTotalAmount` (cargos globales)
		- `PrepaidAmount` (anticipos)
		- `PayableRoundingAmount` / `RoundingAmount` (redondeo)
	- Extracción de retenciones desde `WithholdingTaxTotal`, con clasificación por tipo cuando el proveedor lo informa (fuente, ICA, IVA).
	- Regla de fallback para proveedores que reportan `PayableAmount` como bruto y las retenciones por fuera: se calcula neto con componentes y se toma como total final.
	- Enriquecimiento por ítem:
		- `descuento` por línea (`AllowanceCharge` con `ChargeIndicator=false`)
		- `iva_porcentaje` por línea (`TaxCategory/Percent`)

- **Preview de ingesta con trazabilidad monetaria** (`backend/services/ingestion_service.py`):
	- Nuevos campos por factura:
		- `rete_fuente`, `rete_ica`, `rete_iva`
		- `total_bruto`
		- `total_retenciones`
		- `total_neto`
	- Nuevos campos por ítem en preview:
		- `descuento`
		- `iva_porcentaje`

- **Normalización de respuesta en API de facturas** (`backend/routers/facturas.py`):
	- Nuevo helper interno `_enrich_factura_monetary_fields` para recalcular y devolver estructura monetaria coherente.
	- Aplicado tanto a:
		- `GET /api/facturas`
		- `GET /api/facturas/{factura_id}`

- **Migraciones SQL preparadas para persistencia extendida**:
	- `supabase/003_facturas_totales_exactos.sql`
		- columnas de auditoría y exactitud: `cargos_adicionales`, `anticipos`, `redondeo`, `total_calculado`, `diferencia_centavos`, `validacion_total`, `parsed_version`, `calculo_exacto`
		- índices para consulta operativa
	- `supabase/004_items_factura_descuentos_iva.sql`
		- asegura columnas `descuento` e `iva_porcentaje` en `items_factura`

### Mejorado
- **Dashboard** (`frontend/src/pages/Dashboard.jsx`):
	- Cambio de encabezado a `Total a pagar`.
	- Render principal con `total_neto` (fallback a `total`).

- **Módulo Facturas** (`frontend/src/pages/Facturas.jsx`):
	- Cambio de encabezado de columna a `Total a pagar`.
	- Render principal con `total_neto` (fallback a `total`).

- **Modal de factura** (`frontend/src/components/FacturaModal.jsx`):
	- Campo principal renombrado a `Total a pagar`.
	- Sección nueva `Desglose monetario` con:
		- subtotal
		- IVA
		- total bruto
		- retefuente
		- reteICA
		- reteIVA
		- total retenciones
		- total neto

- **Carga manual DIAN en Facturas** (`frontend/src/pages/Facturas.jsx`):
	- Se refactorizó la sección de carga (XML/ZIP) de un card embebido a un **modal dedicado**.
	- Nuevo botón de acceso rápido en el header con estilo visual diferenciado (`Cargar Facturas XML`).
	- Implementación de zona **Drag & Drop** en el modal para facilitar la selección múltiple de archivos.
	- Mejor control de UX: cierre automático por `Escape`, clic en fondo y limpieza de estados al cerrar.

### Validación operativa realizada
- **Despliegue Docker actualizado**:
	- `docker compose up -d --build` ejecutado sobre backend, frontend y ai-service.
	- Servicios confirmados arriba en puertos esperados (`8000`, `3000`, `8001`).

- **Prueba de API post-despliegue (factura real)**:
	- Factura `ALTX17971` retornó:
		- `total_bruto`: `1.200.906,35`
		- `total_retenciones`: `25.229,13`
		- `total_neto`: `1.175.677,22`
	- Resultado alineado con expectativa de neto pagadero del soporte.

### Compatibilidad y decisiones
- Se priorizó un enfoque **no disruptivo** en primera entrega:
	- corrección inmediata de visualización desde API (incluyendo históricos con `xml_raw`)
	- migraciones listas para endurecer persistencia sin bloquear operación actual
- No se cambió la semántica funcional de causación en Alegra en esta iteración; el alcance fue precisión monetaria y transparencia de datos.

### Próximos pasos recomendados
- Ejecutar en Supabase SQL Editor:
	- `supabase/003_facturas_totales_exactos.sql`
	- `supabase/004_items_factura_descuentos_iva.sql`
- Realizar validación de muestra ampliada con múltiples proveedores y estructuras XML (con y sin retenciones/cargos/descuentos).
- Definir política formal de tolerancia (`diferencia_centavos`) para alertado o bloqueo de causación en futuras fases.

## [2026-04-08] - Limpieza de UI Operativa y Veracidad de Datos en Dashboard
### Corregido
- **Eliminación de componentes con datos ficticios**: Se retiraron del dashboard los bloques visuales heredados de plantilla (`Earnings Overview`, `Revenue Sources`, `Projects`) que mostraban valores no conectados al backend.
- **Búsqueda no funcional removida del topbar**: Se eliminó la barra de búsqueda superior al no existir lógica real de consulta asociada.
- **Control duplicado de colapso de sidebar**: Se quitó el botón redundante de expandir/contraer en el topbar y se mantuvo únicamente el control oficial dentro del sidebar.

### Mejorado
- **Auditoría con filtro compacto y jerarquía visual clara**: Se rediseñó la barra de filtros para reducir altura ocupada y mejorar densidad visual, manteniendo comportamiento responsive.
- **Encabezado de auditoría más limpio**: Se incorporó un chip compacto de conteo de registros y mejor alineación de elementos para lectura rápida.
- **Usabilidad del filtro**: Al cambiar estado en auditoría, la paginación vuelve automáticamente a la página 1 para evitar estados vacíos engañosos en páginas altas.
- **Menú de usuario tipo SB Admin en topbar**: El bloque de usuario ahora despliega un dropdown al hover/click con opción `Salir`, replicando patrón de navegación esperado.
- **Nombre visible de usuario desde Supabase (modo temporal)**: Se agregó `getSupabaseUserName()` para resolver el nombre desde `auth.user_metadata` (o alias de email) y fallback a `VITE_SUPABASE_USER_NAME` mientras no existe autenticación completa.

### ¿Por qué se hicieron estos cambios?
- **Evitar información engañosa**: Se priorizó que toda visualización del sistema represente únicamente datos reales del backend.
- **Reducir ruido de interfaz**: Se eliminaron controles sin funcionalidad o duplicados que generaban confusión en la navegación.
- **Mejorar calidad visual operativa**: Se optimizó el layout de auditoría para uso diario, con menos espacio desperdiciado y mejor escaneo de datos.
- **Preparar transición a auth real**: Se necesitaba reflejar identidad de usuario en UI desde ya, sin bloquearse por la ausencia de sesiones implementadas.

### Impacto / Optimización
- **Mayor confianza en el panel**: El dashboard ahora refleja solo métricas reales y accionables.
- **Interfaz más consistente**: Menos fricción por controles repetidos y elementos decorativos sin valor operativo.
- **Mejor experiencia en escritorio y móvil**: Filtros más compactos y layout más estable en resoluciones pequeñas.
- **Base lista para autenticación futura**: El dropdown y la acción `Salir` ya están en la interfaz; al implementar auth formal solo se debe ajustar el flujo de sesión y redirección posterior al sign-out.

## [2026-04-08] - Integración de autoskills
### Añadido
- **Instalación de autoskills en el proyecto**: Se ejecutó `npx autoskills -y` en la raíz de `Sync-bank`.
- **Lockfile de skills**: Generado `skills-lock.json` con hashes y fuentes de skills instaladas.
- **Skills instaladas**: `frontend-design`, `accessibility` y `seo` en `.agents/skills`.
- **Automatización en Makefile**: Añadidos comandos `make autoskills` y `make autoskills-dry-run`.

### Documentación
- **README actualizado**: Se agregó sección de uso de autoskills, ubicación de skills (`.agents/skills`) y lockfile (`skills-lock.json`).
- **Compatibilidad Windows**: Se añadieron scripts `scripts/autoskills.ps1` y `scripts/autoskills-dry-run.ps1` para ejecutar autoskills sin dependencia de `make`.

## [2026-04-08] - Integración de Catálogo Alegra y Mapeo Operativo
### Añadido
- **Catálogo Alegra en backend**: Nuevo endpoint `GET /api/config/alegra/catalogo` que devuelve cuentas contables y centros de costo reales desde Alegra para uso del frontend.

## [2026-04-13] - Autofill proveedor→cuenta, auditoría y automatización de mapeos
### Añadido
- **Autofill de cuenta contable por NIT**:
	- Nuevo servicio `backend/services/provider_mapping_service.py` que computa la cuenta contable más frecuente por `nit_proveedor` usando historial local (`items_factura`) y, como fallback, consultas a Alegra. Persistencia automática en `config_cuentas` cuando hay suficiente confianza.
	- La lógica de ingestión (`backend/services/ingestion_service.py`) ahora intenta recomputar y aplicar un mapping antes de invocar la clasificación por IA, evitando pasos manuales innecesarios.

- **Endpoint administrativo para recomputar mappings**:
	- Nuevo endpoint `POST /api/providers/recompute` en `backend/routers/providers.py` para recomputar mappings por NIT o en lote desde facturas locales.

- **Autofill en flujo de causación**:
	- `POST /api/facturas/{id}/causar` ahora intenta un autofill (local → Alegra) antes de solicitar confirmación manual por item, reduciendo bloqueos de causación.

- **Auditoría de mappings**:
	- Nuevo helper `save_config_cuenta(...)` en `backend/services/supabase_service.py` realiza `upsert` en `config_cuentas` y escribe un registro en `config_cuentas_audit` para mantener trazabilidad.

- **Scheduler**:
	- Job programado en `backend/scheduler.py` que intenta recomputar mappings periódicamente (cada 6 horas por defecto).

### Modificado
- **UI: Modal de factura** (`frontend/src/components/FacturaModal.jsx`): las cuentas autocompletadas aparecen deshabilitadas por defecto y se añade botón `Editar` para permitir corrección manual; así el usuario solo debe seleccionar centro de costos y presionar `Causar` en la mayoría de los casos.

### Notas
- Asegúrate de ejecutar las migraciones/creación de tabla `config_cuentas_audit` en Supabase para habilitar auditoría.
- Recomendado: revisar `MIN_OCCURRENCES` y `MIN_SHARE` en `provider_mapping_service.py` para ajustar sensibilidad.

- **Consulta de cuentas y centros**: Integración de `GET /categories?type=expense` y `GET /cost-centers` en servicio de Alegra con cache en memoria para reducir llamadas repetidas.
- **Script de diagnóstico**: Disponible `backend/scripts/list_alegra_accounts.py` para listar IDs de cuentas de gastos en la cuenta de Alegra.
- **Catálogo en vista de Cuentas**: La vista de configuración ahora muestra listas reales de cuentas y centros de costo y permite refrescarlas con el botón "Actualizar catálogo Alegra".
- **Selector de cuenta en formulario**: `id_cuenta_alegra` pasó de input libre a selector con opciones reales (`id | nombre`) tomadas de Alegra.

### Corregido
- **Normalización de respuesta Alegra**: Se soportan respuestas tipo lista y respuestas envueltas en `data` al consultar categorías y centros.
- **Clasificación con contexto real**: El backend ahora envía a IA tanto cuentas como centros de costo al clasificar items sin mapeo manual por NIT.
- **Persistencia de clasificación**: Se guarda `cuenta_contable_alegra` y `centro_costo_alegra` en items cuando la clasificación es automática.
- **Payload de bill en Alegra**: Se agregó `costCenter.id` por item cuando existe centro de costo clasificado/definido.
- **Cuenta por defecto operativa**: Actualizado `ALEGRA_CUENTA_DEFAULT_GASTOS` a `5068` en entorno local para evitar fallback a una cuenta inexistente.

## [2026-04-08] - Estabilidad Frontend Supabase y Entorno
### Corregido
- **Inicialización segura de Supabase en frontend**: El cliente ahora se crea solo si existen `VITE_SUPABASE_URL` y `VITE_SUPABASE_ANON_KEY`.
- **Evitar crash en dashboard**: La suscripción realtime se activa únicamente cuando Supabase está configurado; sin variables, el dashboard continúa funcionando por API.
- **Mensaje de configuración faltante**: Se estandarizó el manejo de error cuando `VITE_API_URL` no está definido.


## [2026-04-08] - Robustez en Sincronización y Procesamiento XML
### Corregido
- **Parser XML Defensivo**: Se implementaron fallbacks automáticos para NITs y nombres cuando el XML es incompleto o usa wrappers como `AttachedDocument`.
- **Lógica de "Visto" (IMAP)**: Ahora los correos solo se marcan como leídos (`Seen`) si el procesamiento global es exitoso, evitando la pérdida de facturas por errores temporales.
- **Supabase Auditing**: Se cambió el modo de inserción a `upsert` para permitir reintentos de logs de email sin errores de llave duplicada.
- **Serialización Datetime**: Corregido error `Object of type datetime is not JSON serializable` al guardar en Supabase usando `model_dump(mode='json')`.
- **Integración Alegra**: Añadida validación estricta de campos obligatorios y soporte para búsqueda/creación dinámica de proveedores.

## [2026-04-08] - Correcciones Frontend y Estabilización Tailwind
### Corregido
- Se eliminó el conflicto de versiones Tailwind/PostCSS (mezcla v3/v4) en frontend.
- `postcss.config.js` quedó alineado con Tailwind v3 usando `tailwindcss` como plugin PostCSS.
- Se retiró `@tailwindcss/postcss` de dependencias para evitar errores de compilación CSS.
- Resuelto el error de Vite/PostCSS: `Cannot apply unknown utility class bg-dark-900`.

### Verificado
- Build de frontend exitoso con `vite build`.
- Generación correcta de estilos Tailwind en `src/index.css` y utilidades personalizadas (`dark`, `brand`).

## [2026-04-08] - Fase Completa: Implementación de Núcleo y Servicios
### Añadido
- Backend FastAPI con APScheduler, IMAP listener y XML Parser DIAN.
- Microservicio AI para clasificación de cuentas con Ollama.
- Dashboard React con monitoreo en tiempo real vía Supabase.
- Configuración Docker Compose completa.
- Documentación README y automatización vía Makefile.
