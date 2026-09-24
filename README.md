# Sync-bank 🚀

Sistema de causación automática de facturas electrónicas (DIAN Colombia) para Alegra.

## 🛠 Arquitectura
- **Backend**: FastAPI (Python) - Procesamiento de emails, XML/PDF y causación en Alegra. También sirve el frontend compilado.
- **Frontend**: React + Vite - Panel de gestión.
- **Base de Datos**: PostgreSQL (Railway). El esquema canónico está en `database/schema.sql`.
- **Despliegue**: Railway (`backend/Dockerfile`, un solo servicio + PostgreSQL).

No se usa IA ni un servicio de clasificación externo: la clasificación contable sale de reglas por proveedor y del historial de facturas ya causadas.

## 📋 Requisitos
- Python 3.11+
- Node 18+
- PostgreSQL 16 (local desechable con Docker para pruebas)

## 🚀 Configuración Rápida

1. **Instalar dependencias**:
   ```bash
   make setup
   ```

2. **Variables de entorno** (`.env` en `backend/`, nunca se versiona):
   - `DATABASE_URL` (PostgreSQL).
   - `ALEGRA_EMAIL` y `ALEGRA_TOKEN`.
   - `IMAP_HOST`, `IMAP_PORT`, `IMAP_USER` e `IMAP_PASS` (buzón donde llegan las facturas).
   - `IMAP_MAILBOX` (opcional, por defecto `inbox`): carpeta o etiqueta que se lee. Con Gmail, usa una etiqueta dedicada (por ejemplo `Facturas`, con "Mostrar en IMAP" activo) para no tocar el resto de tu correo. Ojo: "Sincronizar correos" revisa **todos** los mensajes de esa carpeta, no solo los no leídos.
   - `ADMIN_API_KEY` y `ADMIN_USERNAME` (acceso al panel).

3. **Iniciar el sistema**:
   ```bash
   make dev
   ```

## 🔌 API Endpoints (Backend)
- `POST /api/proceso/manual`: Encola la sincronización del correo y responde `202` con `{job, created}`; si ya hay una activa devuelve esa. No espera a IMAP.
- `GET /api/proceso/status`: Trabajo activo o el último terminado (estado, progreso, resultado), leído de PostgreSQL.
- `POST|GET /api/facturas/mantenimiento/pendientes`: Barrido de pendientes (ignora eventos DIAN, marca las que Alegra ya tiene y prellena). Corre solo cada 15 min sobre los últimos 60 días.
- `GET /api/facturas/`: Listado de facturas (con barra final).
- `POST /api/facturas/{id}/causar`: Causa una factura en Alegra (acción explícita del operador).
- `GET /api/facturas/reconciliar-alegra`: Barrido de solo lectura que compara las facturas pendientes con Alegra.
- `GET|POST /api/config/`, `PATCH|DELETE /api/config/{id}`: Reglas por proveedor (NIT → cuenta y centro de costo).

## 🧠 Flujo de Datos
1. **Email Listener**: Cada 5 min el programador **encola** un trabajo (`sync_jobs`); un ejecutor lo toma y lee la etiqueta `IMAP_MAILBOX` buscando ZIP/XML de la DIAN. El XML es la fuente de verdad; los PDF sueltos no se procesan.
2. **Parser**: Extrae datos clave del XML (CUFE, NIT, totales, ítems). Una línea sin impuesto tiene IVA 0 %.
3. **Clasificación**: Se aplica la regla del proveedor (cuenta y, opcionalmente, un centro de costo) a todos los ítems y la factura queda `pendiente`.
4. **Revisión y causación**: El operador revisa la clasificación, la corrige si hace falta y presiona **Causar en Alegra**.
5. **Panel**: Muestra el estado de todo el proceso.

## 🔐 Acceso

- **Personas**: solo con Google. Entra `IMAP_USER` y los correos de `GOOGLE_ALLOWED_EMAILS`. La sesión dura 14 días y el navegador recuerda la última cuenta usada, así Google no vuelve a pedir el correo.
- **El usuario `admin` con contraseña está deshabilitado** (`PASSWORD_LOGIN_ENABLED=false`). Poner `true` solo como vía de emergencia.
- **Scripts y monitoreo**: envían el header `X-Admin-Key` con `ADMIN_API_KEY`. Ya no se acepta autenticación Basic.

## 🔁 Sincronización durable

- **Trabajos**: cada lectura del correo es una fila de `sync_jobs` con estado `pending` → `running` → `succeeded` o `failed`, progreso y resultado. Solo puede existir un trabajo activo; pedirlo dos veces devuelve el mismo.
- **Ejecución**: un ejecutor dentro del proceso reclama trabajos con `FOR UPDATE SKIP LOCKED`. El botón manual (`SINCE MIN_ISSUE_DATE`, incluye correos ya abiertos) y el programador (`UNSEEN`) usan la misma cola.
- **Recuperación**: al arrancar, un trabajo que quedó `running` por un reinicio vuelve a `pending` (o falla si agotó intentos). Un fallo transitorio de IMAP se reintenta hasta 3 veces; los errores de documento no reintentan el trabajo, quedan en el resumen.
- **El panel** consulta `GET /api/proceso/status`, así que cambiar de pantalla o recargar no pierde el avance.

### Adjuntos y receptor

- Solo se aceptan `Invoice` UBL o `AttachedDocument` que contenga una `Invoice` (por elemento raíz). Los eventos DIAN (`ApplicationResponse`) se ignoran y las notas crédito/débito se marcan como no soportadas.
- Límites al abrir ZIP, comprobados con sus metadatos antes de descomprimir: `MAX_ATTACHMENT_BYTES` (20 MiB), `MAX_ZIP_ENTRIES` (100), `MAX_ZIP_EXPANDED_BYTES` (50 MiB), `MAX_ZIP_COMPRESSION_RATIO` (100), anidamiento máximo 3 y sin ZIP cifrados.
- `COMPANY_NIT` (sin dígito de verificación) es obligatorio: un XML sin NIT de receptor o con otro NIT es inválido y nunca se guarda ni se autocausa.
- Ventanas de fechas: solo se leen y muestran facturas emitidas desde `MIN_ISSUE_DATE`; las reglas se aprenden con facturas desde `LEARNING_START_DATE`.

## 🧾 Reglas por proveedor

En **Mapa de cuentas** se administra una regla por NIT:

- **Cuenta** (obligatoria) y **centro de costo** (opcional, uno solo) elegidos del catálogo vigente de Alegra. Toda la factura se causa con esa pareja.
- **Prioridad**: regla manual → regla aprendida del historial → selección manual. Una regla manual nunca se sobrescribe automáticamente; editar una regla la marca como manual.
- **Aprendizaje**: cada factura causada con éxito vota una vez por su pareja cuenta-centro. Con al menos 3 votos y 70 % de coincidencia se guarda una regla aprendida. Las facturas pendientes, fallidas o sin causar no enseñan nada.
- **Sin clasificación**: un proveedor nuevo o ambiguo queda pendiente y el botón de causar permanece bloqueado hasta elegir la cuenta.

### Autocausación (opcional, desactivada por defecto)

La causación es siempre manual, salvo para los proveedores que autorices expresamente (por ejemplo, peajes DEVISAB):

- Se activa por proveedor con **Autocausar en Alegra** en su regla; requiere cuenta y centro de costo.
- Solo aplica a XML DIAN recibido por correo (nunca PDF, carga manual ni historial) y solo si todas las validaciones pasan: CUFE y número reales, COP, totales coherentes a un centavo e ítems con la cuenta y el centro de la regla.
- Si una validación falla o Alegra rechaza la factura, queda `pendiente` y el motivo se guarda en `causaciones` (estado `autocausacion_bloqueada`). Si la factura ya existe en Alegra, queda `procesado`.
- Cambiar el NIT, la cuenta o el centro de una regla la desactiva hasta que se autorice de nuevo.
- **Para detenerla al instante**: edita la regla del proveedor y desmarca **Autocausar en Alegra** (o desactiva la regla).

## 🛠 Comandos Útiles (Makefile)
- `make setup`: Instala dependencias locales de Python y Node.
- `make dev`: Levanta docker-compose con hot-reload.
- `make test-email`: Envía un email de prueba para validar el flujo.
- `make autoskills-dry-run`: Previsualiza skills de IA detectadas por stack.
- `make autoskills`: Instala skills de IA recomendadas en `.agents/skills`.

## 🤖 AI Skills (autoskills)
Este repositorio está configurado para usar `autoskills` y mantener un stack de skills de agente alineado con el proyecto.

- Comando base:
    ```bash
    npx autoskills -y
    ```
- Lockfile de skills instaladas:
    - `skills-lock.json`
- Carpeta de skills instaladas:
    - `.agents/skills`

Skills instaladas actualmente para este sistema:
- `frontend-design`
- `accessibility`
- `seo`

### Ejecución en Windows (PowerShell)
Si no tienes `make` instalado en Windows, usa:

```powershell
./scripts/autoskills-dry-run.ps1
./scripts/autoskills.ps1
```

### PostgreSQL local

`docker compose -f docker-compose.test.yml up -d postgres-test` inicia un PostgreSQL desechable en el puerto 55432. Si Windows bloquea ese puerto, levanta uno propio en otro (`docker run -d -e POSTGRES_DB=syncbank -e POSTGRES_USER=syncbank -e POSTGRES_PASSWORD=syncbank -p 45432:5432 postgres:16-alpine`) y ajusta `DATABASE_URL`.

> **Cuidado:** las pruebas de integración ejecutan `drop schema public cascade` sobre `DATABASE_URL`. Apúntala únicamente a la base desechable, nunca a desarrollo ni a producción.

Aplica el esquema con `psql "$TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f database/schema.sql`.

`database/schema.sql` no se aplica solo en producción. Los cambios aditivos (por ejemplo `auto_causar`) también se registran en `backend/repositories/schema_upgrades.py`, que el backend ejecuta de forma idempotente al arrancar.

Nunca guardes en Git `SOURCE_DATABASE_URL`, volcados con datos de producción ni contraseñas de base de datos.

### Migración y corte a PostgreSQL

1. Pausa la sincronización de correos y las escrituras de usuarios.
2. Crea y verifica un respaldo final de Supabase.
3. Aplica `database/schema.sql` y restaura los datos en un PostgreSQL vacío de Railway.
4. Ejecuta `database/verify.sql` en origen y destino; filas, CUFE únicos y total deben coincidir.
5. Configura `DATABASE_URL` con la URL privada de Railway y despliega el backend.
6. Prueba facturas, estadísticas y logs antes de reanudar la sincronización.
7. Para volver atrás, restaura las variables y el despliegue anterior. Nunca permitas escrituras simultáneas en ambas bases.

---
Hecho con ❤️ por el equipo de Automatización.
