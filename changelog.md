# Changelog

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
