# Sincronización durable y extracción segura

## Objetivo

Hacer que la sincronización de correo continúe fuera de la petición web, sobreviva cambios de pantalla y reinicios de Railway, evite ejecuciones concurrentes y procese únicamente facturas DIAN válidas destinadas a LOGINCARGO.

## Alcance

- Trabajos de sincronización persistidos en PostgreSQL.
- Ejecución asíncrona compartida por el botón manual y el programador automático.
- Recuperación de trabajos interrumpidos y máximo de tres intentos.
- Estado y resultado consultables desde el panel.
- Extracción segura de XML directos y contenidos en ZIP.
- Validación obligatoria del NIT receptor antes de persistir o autocausar.

No se añaden Redis, RabbitMQ, microservicios ni IA.

## Modelo de trabajos

La tabla `sync_jobs` guardará:

- `id` UUID;
- `job_type`, inicialmente `email_sync`;
- `status`: `pending`, `running`, `succeeded` o `failed`;
- `progress` JSONB;
- `result` JSONB;
- `attempts` y `max_attempts`, con máximo predeterminado de tres;
- `error_message`;
- `requested_by`: `manual` o `scheduler`;
- fechas de creación, inicio, finalización y actualización.

Solo podrá existir un trabajo de correo activo (`pending` o `running`). Una restricción parcial y un bloqueo transaccional de PostgreSQL evitarán duplicados.

## Ejecución

`POST /api/proceso/manual` creará o devolverá el trabajo activo y responderá inmediatamente con `202`. No ejecutará IMAP dentro de la petición.

Un ejecutor dentro del proceso actual reclamará trabajos mediante `FOR UPDATE SKIP LOCKED`. Al iniciar la aplicación, los trabajos que hayan quedado `running` por un reinicio volverán a `pending` si aún tienen intentos disponibles.

El programador de cinco minutos encolará el mismo tipo de trabajo. No llamará directamente al lector IMAP.

No se crea otro servicio Railway por ahora: PostgreSQL aporta durabilidad y exclusión, y la única instancia actual ejecuta la cola. Si en el futuro se escala horizontalmente, `SKIP LOCKED` mantiene un único consumidor por trabajo.

## Estado en el panel

`GET /api/proceso/status` leerá PostgreSQL y devolverá el trabajo activo o el último terminado. El panel consultará periódicamente este endpoint mientras haya un trabajo activo, por lo que cambiar de vista o recargar no perderá el estado.

La interfaz mostrará: en cola, ejecutando, progreso, terminado o fallido, junto con el resumen de facturas creadas, duplicadas, inválidas, autocausadas y pendientes.

## Extracción ZIP/XML

El extractor aceptará únicamente:

- `Invoice` UBL;
- `AttachedDocument` que contenga una `Invoice` UBL.

Ignorará de forma explícita `ApplicationResponse` y separará como no soportadas las notas crédito y débito. Validará el tipo mediante el elemento raíz, no solamente mediante extensión o texto.

Límites:

- tamaño máximo del adjunto;
- máximo de entradas por ZIP;
- tamaño máximo total descomprimido;
- relación máxima de compresión;
- profundidad máxima de ZIP anidado;
- rechazo de entradas cifradas.

Cuando un correo contenga XML y PDF, el XML será la fuente contable y el PDF no pasará por OCR. El OCR seguirá disponible para PDF sin XML, siempre como documento pendiente de revisión y nunca para autocausación.

## Validación del receptor

Se añadirá `COMPANY_NIT` a la configuración. El parser dejará de sustituir receptores ausentes por `123456789`.

Antes de persistir un XML se normalizará el NIT receptor y se exigirá que coincida con `COMPANY_NIT`. Un receptor ausente o diferente producirá un resultado inválido con motivo explícito y nunca llegará a autocausación.

En producción se configurará `COMPANY_NIT=900741732`.

## Errores y reintentos

- Un error transitorio de IMAP o red reencolará el trabajo hasta completar tres intentos.
- Errores documentales no reintentarán el trabajo completo; cada archivo quedará registrado como inválido en el resumen.
- Tras agotar intentos, el trabajo quedará `failed` con el último error.
- Un trabajo fallido podrá volver a solicitarse desde el panel creando un trabajo nuevo.

## Compatibilidad y despliegue

La migración será idempotente y se aplicará al arrancar, siguiendo el mecanismo actual de `schema_upgrades.py`. Los endpoints conservarán sus rutas; cambiará la respuesta del disparador manual a trabajo aceptado.

El despliegue requiere añadir `COMPANY_NIT` y ejecutar verificaciones de salud, creación de trabajo, consulta de progreso y procesamiento de fixtures. No se causarán facturas reales durante las pruebas automáticas.

## Pruebas

- Creación idempotente de un trabajo activo.
- Reclamación exclusiva con dos consumidores.
- Recuperación después de reinicio.
- Éxito, error y máximo de tres intentos.
- El endpoint manual responde sin esperar la lectura IMAP.
- El estado se recupera desde PostgreSQL.
- Factura UBL directa y dentro de `AttachedDocument`.
- Rechazo de respuestas, notas y ZIP peligrosos.
- Receptor correcto, ausente e incorrecto.
- Regresión completa del backend y del frontend.
