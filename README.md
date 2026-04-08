# Sync-bank 🚀

Sistema de causación automática de facturas electrónicas (DIAN Colombia) para Alegra.

## 🛠 Arquitectura
- **Backend**: FastAPI (Python) - Procesamiento de emails y XMLs.
- **Frontend**: React + Vite + TailwindCSS - Dashboard de monitoreo.
- **AI Service**: FastAPI + Ollama - Clasificación de cuentas contables.
- **Base de Datos**: Supabase (PostgreSQL).
- **Control**: Docker Compose.

## 📋 Requisitos
- Python 3.11+
- Node 18+
- Docker
- Ollama (instalado localmente o vía Docker)

## 🚀 Configuración Rápida

1. **Clonar el repositorio** e instalar dependencias:
   ```bash
   make setup
   ```

2. **Configurar variables de entorno**:
   Copia `.env.example` a `.env` y completa los valores:
   - `SUPABASE_URL` y `SUPABASE_KEY` (desde Supabase Dashboard).
   - `ALEGRA_EMAIL` y `ALEGRA_TOKEN`.
   - `IMAP_USER` y `IMAP_PASS` (Gmail App Password).

3.  **Preparar el modelo de IA**:
    ```bash
    make pull-model
    ```

4.  **Iniciar el sistema**:
    ```bash
    make dev
    ```

## 🔌 API Endpoints (Backend)
- `POST /api/proceso/manual`: Dispara la revisión de emails inmediatamente.
- `GET /api/facturas`: Listado de facturas procesadas.
- `POST /api/config/cuentas`: Crear mapeo de NIT a cuenta contable.

## 🧠 Flujo de Datos
1. **Email Listener**: Revisa la bandeja de entrada cada 5 min buscando XMLs de la DIAN.
2. **Parser**: Extrae datos clave del XML (CUFE, NIT, Totales, Items).
3. **AI Clasificador**: Analiza las descripciones de los items y sugiere la cuenta contable de Alegra.
4. **Causación**: Envía la factura a la API de Alegra como un "Bill".
5. **Dashboard**: Muestra el estado de todo el proceso en tiempo real.

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

---
Hecho con ❤️ por el equipo de Automatización.
