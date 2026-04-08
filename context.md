Sync-bank/
├── backend/          # FastAPI (Python)
├── frontend/         # React + Vite
├── ai-service/       # Ollama wrapper
├── supabase/         # Schema + migrations
└── docker-compose.yml
Eres un experto en PostgreSQL y Supabase.

Crea el schema SQL completo para un sistema de causación automática 
de facturas electrónicas colombianas (DIAN).

Tablas requeridas:
1. `facturas` — almacena facturas recibidas por email
   - id, cufe (único), numero_factura, fecha_emision, fecha_vencimiento
   - nit_proveedor, nombre_proveedor, nit_receptor
   - subtotal, iva, rete_fuente, rete_ica, rete_iva, total
   - moneda, estado (pendiente|procesado|error|duplicado)
   - xml_raw (text), pdf_url, created_at, updated_at

2. `items_factura` — líneas de cada factura
   - id, factura_id (FK), descripcion, cantidad, precio_unitario
   - descuento, iva_porcentaje, total_linea
   - cuenta_contable_alegra (nullable), centro_costo_alegra (nullable)

3. `causaciones` — registro de lo enviado a Alegra
   - id, factura_id (FK), alegra_bill_id, alegra_response (jsonb)
   - estado (exitoso|fallido|reintento), intentos, error_msg
   - created_at

4. `config_cuentas` — mapeo NIT → cuenta contable Alegra
   - id, nit_proveedor, nombre_cuenta, id_cuenta_alegra
   - id_retefuente, id_reteica, id_reteiva, activo

5. `logs_email` — auditoría de emails procesados
   - id, mensaje_id (único), remitente, asunto
   - estado (procesado|ignorado|error), attachments_encontrados
   - created_at

Incluye:
- Row Level Security (RLS) básico
- Índices en cufe, nit_proveedor, estado, created_at
- Triggers para updated_at automático
- Seed data con 2 ejemplos de config_cuentas


Eres un experto en Python, FastAPI y procesamiento de XML DIAN Colombia.

Crea un servicio FastAPI completo con esta estructura:

backend/
  main.py
  config.py              # Variables de entorno con pydantic-settings
  models/
    factura.py           # Pydantic models
  services/
    email_service.py     # IMAP listener
    xml_parser.py        # Parser XML DIAN UBL 2.1
    ai_service.py        # Cliente Ollama
    alegra_service.py    # Cliente API Alegra
    supabase_service.py  # CRUD Supabase
  routers/
    facturas.py          # CRUD endpoints
    proceso.py           # Trigger manual
    config.py            # Configuración cuentas
  scheduler.py           # APScheduler cada 5 min

REQUERIMIENTOS ESPECÍFICOS:

1. email_service.py:
   - Conectar via IMAP SSL (Gmail/Outlook/cualquier SMTP)
   - Buscar emails no leídos con adjuntos .xml o .zip
   - Descomprimir .zip si es necesario
   - Extraer XMLs adjuntos y pasarlos al parser
   - Marcar email como leído tras procesar
   - Guardar log en tabla logs_email de Supabase

2. xml_parser.py:
   - Parsear XML UBL 2.1 de facturas electrónicas DIAN Colombia
   - Extraer: CUFE, número factura, NIT proveedor/receptor
   - Extraer: fecha emisión, fecha vencimiento
   - Extraer: subtotal, IVA 19%, retenciones (ReteIVA, ReteFuente, ReteICA)
   - Extraer: líneas de items con descripción, cantidad, precio, %IVA
   - Detectar duplicados por CUFE antes de insertar
   - Retornar Pydantic model FacturaDIAN

3. ai_service.py:
   - Cliente HTTP para Ollama local (http://localhost:11434)
   - Función: clasificar_cuenta(descripcion_item, lista_cuentas_alegra)
     que dado un texto como "Servicios de publicidad digital"
     retorna el id_cuenta_alegra más apropiado
   - Usar modelo configurable (default: qwen3:4b o gemma3:4b)
   - Fallback: si Ollama no responde, usar cuenta por defecto

4. alegra_service.py:
   - Auth: Basic Auth (email:token en Base64)
   - Base URL: https://api.alegra.com/api/v1
   - Función: crear_bill(factura_dian) → POST /bills
   - Mapear campos DIAN → estructura Alegra bills Colombia
   - Incluir retenciones como items negativos o campo retentions
   - Retornar alegra_bill_id o lanzar excepción con detalle

5. scheduler.py:
   - Revisar emails cada 5 minutos con APScheduler
   - Endpoint POST /proceso/manual para trigger inmediato
   - Endpoint GET /proceso/status para ver última ejecución

Variables .env requeridas:
IMAP_HOST, IMAP_PORT, IMAP_USER, IMAP_PASS
ALEGRA_EMAIL, ALEGRA_TOKEN
SUPABASE_URL, SUPABASE_KEY
OLLAMA_URL, OLLAMA_MODEL
ALEGRA_CUENTA_DEFAULT_GASTOS

Usa: fastapi, uvicorn, supabase-py, python-dotenv,
pydantic-settings, aiohttp, apscheduler, lxml, python-dateutil

Eres un experto en React, Vite, TailwindCSS y Supabase JS.

Crea un dashboard React completo para monitorear causaciones automáticas 
de facturas DIAN → Alegra. Diseño dark, profesional, minimalista industrial.

Stack: React 18 + Vite + TailwindCSS + Supabase JS client + React Query

Páginas/vistas:

1. /dashboard — Vista principal
   - KPI cards: Facturas hoy / Causadas / Pendientes / Errores
   - Tabla últimas 20 facturas con estado (badge de color)
   - Botón "Revisar emails ahora" → POST /api/proceso/manual
   - Indicador de última sincronización

2. /facturas — Lista completa
   - Tabla con filtros: estado, fecha, proveedor
   - Click en fila → modal con detalle completo
   - En modal: botón "Causar en Alegra" para casos pendientes
   - Paginación server-side

3. /configuracion — Mapeo de cuentas
   - CRUD de tabla config_cuentas
   - Form: NIT proveedor, nombre cuenta, cuenta Alegra (dropdown o ID)
   - Toggle activo/inactivo

4. /logs — Auditoría
   - Timeline de emails procesados
   - Estado por email con detalles de error si falló

Componentes reutilizables:
- <StatusBadge status="pendiente|procesado|error|duplicado" />
- <FacturaModal factura={} onClose={} />
- <KpiCard label="" value="" delta="" icon="" />
- <DataTable columns={} data={} onRowClick={} />

Supabase realtime:
- Suscribir tabla facturas para actualizar dashboard en tiempo real
- Mostrar toast cuando llega factura nueva

Colores de estado:
- pendiente: amarillo
- procesado: verde  
- error: rojo
- duplicado: gris

Variables de entorno:
VITE_SUPABASE_URL
VITE_SUPABASE_ANON_KEY
VITE_API_URL (backend FastAPI)

Eres experto en Python y modelos de lenguaje locales con Ollama.

Crea un microservicio FastAPI independiente para clasificación de 
cuentas contables usando LLM local.

Archivo: ai-service/main.py

Endpoints:
1. POST /clasificar
   Body: { "descripcion": "Servicios de nube AWS", "cuentas": [...lista de cuentas Alegra...] }
   Response: { "cuenta_id": "123", "cuenta_nombre": "Gastos tecnología", "confianza": 0.92 }

2. POST /extraer-pdf  
   Body: { "pdf_base64": "..." }
   Response: FacturaDIAN model (para PDFs que no tienen XML)

3. GET /health → estado de Ollama + modelo cargado

Lógica del clasificador:
- System prompt: "Eres un contador colombiano experto en PUC (Plan Único de Cuentas). 
  Dado el siguiente item de factura, selecciona la cuenta contable más apropiada 
  de la lista. Responde SOLO con el ID de la cuenta en formato JSON: {"cuenta_id": "xxx"}"
- Temperatura: 0.1 (determinista)
- Si confianza < 0.7, retornar cuenta por defecto configurada

Para extraer-pdf:
- Usar pymupdf (fitz) para extraer texto del PDF
- Prompt: extraer CUFE, NIT, fecha, items, totales, retenciones
- Responder en JSON estructurado igual que el XML parser

Dependencias: fastapi, ollama, pymupdf, pydantic

Crea el docker-compose.yml y README completo para el sistema 
DIAN → Alegra con estos servicios:

docker-compose.yml:
- backend: FastAPI en puerto 8000, con hot-reload
- frontend: Vite dev server en puerto 3000
- ai-service: FastAPI en puerto 8001
- ollama: imagen ollama/ollama, puerto 11434, 
  con volumen para modelos persistidos
  comando post-start: ollama pull qwen3:4b

Variables de entorno en .env.example con todos los valores necesarios.

README.md en español con:
1. Requisitos (Python 3.11+, Node 18+, Docker, Ollama)
2. Setup paso a paso
3. Cómo obtener token de Alegra API
4. Cómo configurar Gmail para IMAP (App Password)
5. Cómo correr el modelo: ollama run qwen3:4b
6. Endpoints principales de la API con ejemplos curl
7. Flujo completo explicado: Email → XML → IA → Alegra
8. Troubleshooting común

Makefile con comandos:
- make setup     → instalar dependencias
- make dev       → levantar todo en desarrollo  
- make pull-model → descargar modelo Ollama
- make test-email → enviar email de prueba con XML de ejemplo

1. PROMPT 1  → Supabase (5 min, sin dependencias)
2. PROMPT 5  → Docker + README (estructura base)
3. PROMPT 2  → Backend (núcleo del sistema)
4. PROMPT 4  → AI Service (independiente)
5. PROMPT 3  → Frontend (consume el backend)