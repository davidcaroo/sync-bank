# Diseño de simplificación y migración de Sync-bank

Fecha: 2026-09-17

Estado: aprobado por el usuario

Alcance: arquitectura, ingesta documental, persistencia y despliegue

## 1. Objetivo

Convertir Sync-bank en un monolito modular desplegable en Railway que:

- lea automáticamente el buzón mediante IMAP;
- procese XML DIAN, ZIP con XML y PDF;
- use XML como fuente de verdad cuando esté disponible;
- extraiga PDF mediante texto nativo y OCR, sin IA;
- permita separar paquetes PDF que contengan varias facturas;
- obligue a revisión humana para toda factura proveniente solo de PDF;
- persista en PostgreSQL sin depender de Supabase;
- cause facturas validadas en Alegra;
- sirva la API FastAPI y el frontend React compilado desde una sola aplicación pública.

## 2. Decisiones aprobadas

1. FastAPI continúa como backend. No se reescribe en Node.js.
2. React continúa como frontend y se compila para producción.
3. FastAPI sirve el frontend compilado y la API desde el mismo origen.
4. PostgreSQL en Railway reemplaza la Data API de Supabase.
5. IMAP es una función obligatoria y constituye una entrada principal.
6. XML DIAN tiene prioridad sobre PDF.
7. Se elimina AI Service como servicio independiente.
8. Se eliminan Ollama y la clasificación contable mediante IA.
9. PDF usa extracción de texto y OCR local en el backend.
10. Todo documento proveniente exclusivamente de PDF requiere confirmación humana antes de persistirse como factura operativa o causarse en Alegra.
11. Los PDF con varias facturas son una excepción poco frecuente; se resuelven con detección determinística de límites y revisión humana, no con un parser universal.
12. La aplicación será un monolito modular. Los módulos son límites de código, no microservicios.

## 3. Fuera de alcance

- Interpretación automática de cualquier formato PDF sin revisión.
- Causación automática desde PDF escaneado.
- Clasificación contable mediante modelos de lenguaje.
- Procesamiento confiable de dos facturas ubicadas dentro de una misma página.
- Multitenencia.
- Reescritura del frontend o backend en otro lenguaje.
- Redis, Dramatiq o una cola distribuida mientras el volumen no demuestre su necesidad.
- Realtime de Supabase.

## 4. Arquitectura objetivo

```text
Navegador
    |
    v
Aplicación pública Railway
    FastAPI + React compilado
    |-- API /api
    |-- archivos estáticos React
    |-- scheduler IMAP
    |-- parser XML
    |-- lector PDF/OCR
    |-- integración Alegra
    |
    +------> PostgreSQL Railway (privado)
    +------> Buzón IMAP
    +------> API Alegra
```

Solo la aplicación tendrá dominio público. PostgreSQL permanece privado.

## 5. Organización del backend

```text
backend/
|-- api/
|   |-- facturas.py
|   |-- configuracion.py
|   |-- contactos.py
|   `-- proceso.py
|-- domain/
|   |-- factura.py
|   `-- resultados.py
|-- ingestion/
|   |-- orchestrator.py
|   |-- attachments.py
|   |-- xml_parser.py
|   |-- pdf_text.py
|   |-- pdf_splitter.py
|   |-- pdf_parser.py
|   `-- validation.py
|-- accounting/
|   `-- account_mapping.py
|-- integrations/
|   |-- alegra/
|   |-- imap.py
|   `-- ocr.py
|-- repositories/
|   |-- database.py
|   |-- facturas.py
|   |-- configuracion.py
|   `-- logs.py
|-- jobs/
|   `-- email_sync.py
|-- config.py
`-- main.py
```

Esta estructura es una dirección de responsabilidades. No obliga a crear un archivo vacío por cada nombre ni a conservar fachadas que solo deleguen.

### Responsabilidades

- `api`: valida HTTP y delega; no contiene reglas contables.
- `domain`: modelos normalizados compartidos por XML y PDF.
- `ingestion`: convierte adjuntos en candidatos de factura.
- `accounting`: resuelve cuenta y centro de costo desde configuración e historial.
- `integrations`: encapsula IMAP, Alegra y OCR.
- `repositories`: contiene SQL parametrizado y transacciones.
- `jobs`: programa y coordina la lectura periódica del buzón.

## 6. Flujo de correo

1. El scheduler ejecuta la revisión IMAP cada cinco minutos.
2. Se buscan mensajes no leídos.
3. Por cada mensaje se descargan adjuntos XML, ZIP y PDF dentro de límites de tamaño.
4. Primero se extraen y procesan todos los XML, incluidos los contenidos en ZIP.
5. Después se examinan los PDF.
6. Un PDF cuyo CUFE o número ya fue obtenido desde XML se conserva como soporte y no crea otra factura.
7. Un PDF sin XML relacionado genera candidatos pendientes de revisión.
8. El mensaje solo se marca como leído cuando sus adjuntos terminan en estado procesado, duplicado, pendiente de revisión o ignorado de forma explícita.
9. Los errores transitorios mantienen el mensaje sin leer para permitir reintento.
10. `Message-ID`, CUFE y huella SHA-256 del adjunto evitan reprocesamientos.

## 7. Flujo XML

1. Extraer XML directo o desde ZIP anidado.
2. Parsear UBL/DIAN.
3. Normalizar a `FacturaDraft`.
4. Validar campos, fechas y coherencia monetaria.
5. Verificar duplicado por CUFE.
6. Resolver cuenta por configuración del proveedor y luego por historial.
7. Persistir factura e ítems en una sola transacción.
8. Dejar la factura pendiente de causación o causarla mediante una acción explícita del operador.

La ausencia de una cuenta contable nunca se resuelve inventando una sugerencia.

## 8. Flujo PDF sin IA

### 8.1 Extracción

- Validar firma, tamaño y cantidad máxima de páginas.
- Extraer texto nativo página por página con PyMuPDF.
- Aplicar Tesseract únicamente si una página no contiene texto suficiente.
- Conservar número de página, texto, uso de OCR y advertencias.

El límite inicial será configurable y tendrá valor predeterminado de 20 páginas. Cinco páginas quedan soportadas sin configuración adicional.

### 8.2 Separación de paquetes

Cada página se clasifica como posible inicio de factura usando señales determinísticas:

- CUFE;
- expresión “factura electrónica de venta”;
- número de factura;
- NIT del emisor;
- fecha de emisión;
- reinicio visible de encabezado.

Una nueva factura comienza cuando aparece una combinación suficiente de señales y el identificador difiere del grupo actual. Las páginas siguientes pertenecen al grupo hasta detectar otro inicio.

Casos esperados:

- una factura de cinco páginas produce un candidato;
- cinco facturas de una página producen cinco candidatos;
- facturas con cantidades variables de páginas se agrupan hasta el siguiente encabezado;
- una separación ambigua produce un solo documento pendiente de división manual.

No se intentará dividir dos facturas dentro de una misma página.

### 8.3 Interpretación y validación

El parser PDF usa patrones conservadores para obtener:

- CUFE;
- número de factura;
- fecha de emisión y vencimiento;
- NIT y nombre del proveedor;
- NIT del receptor;
- subtotal, IVA, retenciones y total;
- ítems solo cuando la tabla pueda reconocerse con una regla verificable.

La salida siempre incluye texto original, páginas de origen, campos faltantes y advertencias. No se asigna confianza numérica artificial.

### 8.4 Revisión obligatoria

Todo candidato originado solo desde PDF recibe el estado `requiere_revision` y no puede causarse hasta que un operador:

1. revise la separación de páginas;
2. corrija o confirme los campos;
3. revise los ítems y totales;
4. seleccione cuenta y centro de costo;
5. confirme la importación.

Después de la confirmación se ejecutan nuevamente validación y deduplicación dentro de la transacción.

## 9. Candidatos PDF y estados operativos

Los resultados de PDF detectados por IMAP deben sobrevivir hasta que un operador los revise, pero no se guardan todavía como facturas. Se registran en `documentos_pendientes` con:

- `message_id` y huella SHA-256 del adjunto;
- nombre del archivo y rango de páginas;
- texto extraído;
- campos candidatos en JSON;
- campos faltantes y advertencias;
- estado de revisión;
- fechas de creación y resolución.

No se persiste el binario PDF: el correo original continúa siendo el soporte. Al confirmar, se crea la factura y sus ítems en una transacción y el candidato queda enlazado a la nueva factura.

Estados de factura:

- `pendiente`: factura validada lista para causar;
- `procesando`: causación en curso;
- `procesado`: causación exitosa;
- `error`: requiere intervención o reintento;
- `duplicado`: el CUFE ya existe.

Estados del adjunto:

- `procesado`;
- `pendiente_revision`;
- `duplicado`;
- `ignorado`;
- `error_transitorio`;
- `error_permanente`.

Estados del candidato PDF:

- `requiere_revision`;
- `confirmado`;
- `descartado`;
- `duplicado`.

## 10. Persistencia PostgreSQL

- `DATABASE_URL` será la única configuración de conexión.
- El backend usará `psycopg` y un pool pequeño.
- Todas las consultas usarán parámetros.
- Factura, ítems y auditoría inmediata se guardan en una transacción.
- Montos contables usan `numeric` en PostgreSQL y `Decimal` en Python.
- CUFE mantiene índice único parcial para valores no vacíos.
- Los candidatos PDF viven en `documentos_pendientes`, separados de `facturas`.
- Los agregados del dashboard se calculan en SQL.
- La base no será accesible desde el navegador.

Antes de migrar se extraerá desde Supabase el esquema real completo y los datos. Los siete SQL existentes son parches y no sustituyen el esquema base.

## 11. Mapeo contable

Orden de resolución:

1. configuración manual activa por NIT;
2. cuenta histórica dominante del proveedor;
3. selección manual del operador.

Se elimina la clasificación mediante IA. Una cuenta histórica solo se aplica automáticamente cuando cumple el mínimo de ocurrencias y proporción configurado. En caso contrario se muestra como dato informativo y se exige selección manual.

## 12. Alegra

La integración se separa internamente en:

- transporte HTTP y autenticación;
- catálogos;
- contactos;
- creación y consulta de bills;
- normalización de errores.

La operación conserva idempotencia por CUFE y consulta de causación exitosa. Los errores de red usan timeout y reintentos acotados; los errores de validación no se reintentan automáticamente.

## 13. Seguridad

- API y frontend se sirven desde el mismo origen.
- Se elimina CORS comodín.
- Todas las rutas de lectura y escritura requieren sesión autenticada, excepto `/healthz`.
- La primera versión usa una sola cuenta administrativa configurada en el servidor.
- El inicio de sesión verifica una contraseña con hash Argon2 y entrega una cookie de sesión firmada, `HttpOnly`, `Secure` y `SameSite=Lax`, con expiración.
- Usuarios múltiples y roles se añadirán únicamente cuando exista esa necesidad operativa.
- Credenciales IMAP, Alegra y base de datos solo existen como variables del servidor.
- Los logs no incluyen contraseñas, tokens, XML completo ni datos personales innecesarios.
- Se limita tamaño, tipo y cantidad de archivos antes de procesarlos.

## 14. Frontend

- React se compila durante el build.
- FastAPI sirve `dist` y conserva `/api` como prefijo reservado.
- Las rutas SPA desconocidas retornan `index.html`; los archivos inexistentes bajo `/api` mantienen 404 JSON.
- La vista de carga muestra candidatos PDF separados por rangos de página.
- Cada candidato muestra campos faltantes, advertencias y texto extraído.
- No existe botón de causación para un candidato `requiere_revision` sin confirmar.
- El dashboard se actualiza después de acciones y mediante refresco periódico liviano; no usa Supabase Realtime.

## 15. Scheduler y concurrencia

- La primera versión ejecuta una réplica de la aplicación.
- El job IMAP usa un advisory lock de PostgreSQL para impedir ejecuciones simultáneas durante despliegues o reinicios.
- Cada correo y adjunto es idempotente.
- El procesamiento se mantiene secuencial inicialmente.
- Se introducirá cola solo si las métricas demuestran acumulación, bloqueos o tiempos incompatibles con el volumen real.

## 16. Manejo de errores

- Un adjunto defectuoso no impide registrar el resultado de los demás adjuntos del correo.
- Los errores temporales de IMAP, PostgreSQL o Alegra son distinguibles de documentos inválidos.
- Ningún `except` silencioso convierte un fallo en éxito.
- Los errores del usuario son breves y accionables.
- Los logs estructurados incluyen `request_id`, `message_id`, huella de adjunto, CUFE y etapa, cuando existan.
- El XML y PDF originales se conservan únicamente según la política de retención definida para auditoría; no se escriben en logs.

## 17. Despliegue Railway

Servicios iniciales:

1. aplicación Sync-bank;
2. PostgreSQL.

La imagen usa un build multietapa:

1. compilar React;
2. instalar dependencias Python y Tesseract;
3. copiar `dist` al runtime FastAPI;
4. iniciar Uvicorn sin `--reload` y escuchando `$PORT`.

Se configuran health check, backups, una réplica y dominio público solo para la aplicación.

## 18. Eliminaciones previstas

- directorio `ai-service` después de mover extracción PDF/OCR necesaria;
- dependencias Ollama;
- cliente HTTP interno hacia AI Service;
- contenedor Ollama;
- Supabase Python y JavaScript SDK;
- Auth y Realtime cosméticos de Supabase;
- Redis, Dramatiq, worker, endpoint asíncrono y `job_tasks`, ya que el frontend y el flujo operativo usan causación sincrónica;
- dependencias frontend no importadas;
- Protocols, adapters y fachadas de una sola implementación que no protejan un límite real;
- plantilla SB Admin completa ya separada del frontend activo.

## 19. Estrategia de implementación

La migración se ejecutará en cortes verificables:

1. fijar una línea base reproducible de pruebas;
2. crear esquema PostgreSQL canónico y repositorios transaccionales;
3. migrar datos de Supabase y verificar paridad;
4. consolidar ingesta XML e IMAP sobre PostgreSQL;
5. mover PDF/OCR al backend y eliminar AI Service;
6. implementar separación y revisión PDF;
7. modularizar FacturaService y AlegraClient sin cambiar contratos externos innecesariamente;
8. compilar y servir React desde FastAPI;
9. aplicar autenticación y cerrar CORS;
10. eliminar cola y dependencias muertas confirmadas;
11. preparar Railway, ensayar restauración y ejecutar corte final.

Cada corte debe dejar el sistema ejecutable y comprobable. No habrá reescritura total en una sola entrega.

## 20. Pruebas y aceptación

### Pruebas mínimas

- XML DIAN directo y dentro de ZIP.
- ZIP anidado y archivo inválido.
- correo con XML y PDF de la misma factura sin duplicación.
- PDF textual de cinco páginas con una factura.
- PDF escaneado de cinco páginas con varias facturas.
- encabezado ambiguo que deriva a revisión manual.
- confirmación PDF con campos faltantes bloqueada.
- dos ingestas concurrentes del mismo CUFE.
- rollback de factura e ítems ante fallo.
- cuenta manual, histórica y sin mapeo.
- causación Alegra exitosa, duplicada, inválida y con timeout.
- autenticación requerida en todas las rutas protegidas.
- job IMAP simultáneo bloqueado mediante PostgreSQL.
- build de React y navegación SPA servida por FastAPI.
- migración con paridad de filas, CUFE y sumas monetarias.

### Criterios de aceptación

- Un correo con XML/ZIP se procesa sin AI Service.
- Un correo con PDF se convierte en uno o más candidatos de revisión.
- Ninguna factura solo-PDF se persiste como operativa ni se causa sin confirmación.
- Un paquete PDF puede agrupar páginas por factura o quedar pendiente de división manual.
- Una factura ya presente por XML no se duplica por su PDF.
- El sistema funciona con aplicación y PostgreSQL como únicos servicios Railway.
- El frontend y la API funcionan bajo un único origen.
- La suite, el build y las pruebas de migración pasan en el entorno Python 3.11 definido por el proyecto.

## 21. Riesgos residuales

- El OCR puede fallar con imágenes borrosas, inclinadas o de baja resolución.
- Los formatos PDF no estandarizados pueden requerir corrección manual o una regla específica futura.
- La extracción genérica de tablas de ítems no será completa para todos los proveedores.
- La migración depende de obtener el esquema y dump reales de Supabase.
- Una sola réplica limita throughput, pero coincide con el volumen actual y evita infraestructura prematura.

Estos riesgos se controlan mediante XML prioritario, revisión obligatoria de PDF, validación estricta, idempotencia y despliegue incremental.
