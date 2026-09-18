# Diseño de autocompletado contable por proveedor

Fecha: 2026-09-18

Estado: aprobado por el usuario

Alcance: clasificación previa de cuenta contable y centro de costo por NIT

## 1. Objetivo

Cuando Sync-bank detecte una factura por correo, XML o PDF, debe identificar el
proveedor por su NIT y completar por defecto:

- una cuenta contable de Alegra;
- cero o un centro de costo de Alegra;
- la fuente y confianza de la clasificación.

La factura permanece en estado `pendiente`. Un operador abre la factura, revisa
la clasificación y presiona **Causar en Alegra**. No habrá causación automática.

## 2. Decisiones aprobadas

1. Cada factura usa una sola cuenta contable y, como máximo, un centro de costo.
2. No se distribuirá una factura entre varios centros de costo.
3. No se utilizará IA ni un servicio de clasificación externo.
4. La configuración manual por NIT tiene prioridad absoluta.
5. El historial sólo aprende de facturas causadas correctamente.
6. La clasificación aprendida se aplica sólo cuando el patrón es suficientemente
   repetido y consistente.
7. El operador conserva la posibilidad de corregir cuenta y centro antes de
   causar.
8. La acción final de causar siempre es humana.

## 3. Casos esperados

### Nitido Car Wash

Una regla activa relaciona su NIT con su cuenta y centro de costo. Cada nueva
factura recibe ambos valores automáticamente y queda pendiente de confirmación.

### Coordinadora

Una regla activa relaciona su NIT con una cuenta y un único centro de costo. El
100 % de la factura se causa con esa clasificación.

### Proveedor conocido sólo por historial

Si al menos tres facturas causadas comparten la misma pareja cuenta-centro y esa
pareja representa al menos el 70 % del historial válido, se guarda y aplica como
regla aprendida.

### Proveedor nuevo o ambiguo

La factura queda pendiente sin inventar una clasificación. El operador selecciona
los valores y causa. Las causaciones exitosas pasan a formar parte del historial.

## 4. Fuente de verdad y prioridad

El orden de resolución será:

1. regla manual activa en `config_cuentas`;
2. regla histórica persistida en `config_cuentas`;
3. sugerencia histórica local no persistida;
4. selección manual.

Una regla con `source = 'manual'` nunca puede ser reemplazada por el scheduler ni
por el aprendizaje automático. Una edición humana actualiza la regla y vuelve a
marcarla como manual.

## 5. Modelo de datos

No se necesitan tablas nuevas. `config_cuentas` ya contiene:

- `nit_proveedor`;
- `nombre_proveedor`;
- `id_cuenta_alegra`;
- `id_centro_costo_alegra`;
- `confianza`;
- `activo`;
- `source`.

La pareja `(id_cuenta_alegra, id_centro_costo_alegra)` representa toda la
clasificación de un proveedor. El centro puede ser nulo; la cuenta no.

Los ítems conservan sus columnas actuales por compatibilidad con el payload de
Alegra. La misma clasificación de la factura se copia a todos sus ítems. No se
añade un modelo de repartos ni JSON contable.

## 6. Aprendizaje histórico

El historial actual cuenta ítems y sólo considera la cuenta. Se reemplazará por
un voto por factura causada:

1. consultar únicamente facturas con causación exitosa;
2. obtener las parejas cuenta-centro de sus ítems;
3. aceptar la factura como voto sólo si todos sus ítems tienen la misma pareja;
4. ignorar facturas sin cuenta o con clasificación mixta;
5. elegir la pareja dominante con los umbrales existentes: tres ocurrencias y
   70 % de participación.

Esto evita que una factura con muchos ítems pese más que otra y evita aprender de
un valor precargado que nunca fue confirmado.

El fallback histórico de Alegra también se interpreta por factura: cuenta
contable dominante y centro de costo general de la factura. La documentación de
Alegra sólo contempla un centro general para el bill, coherente con este diseño.

## 7. Ingesta

XML y PDF deben usar la misma resolución contable:

1. extraer y normalizar NIT;
2. consultar `config_cuentas`;
3. si existe regla activa, copiar cuenta y centro a todos los ítems;
4. si no existe, consultar el historial local;
5. guardar `prefill_source` y `confidence` junto a cada ítem;
6. persistir la factura como `pendiente`.

La resolución debe ser idéntica en previsualización, carga manual e IMAP. El PDF
continúa sujeto a sus reglas de revisión documental existentes.

## 8. Revisión y causación

La modal de factura mostrará claramente:

- cuenta sugerida;
- centro de costo sugerido o “Sin centro de costo”;
- origen: regla manual, historial o selección manual;
- aviso de que la clasificación debe revisarse.

El operador puede editar los valores antes de causar. El botón de causación no se
ejecuta solo y permanece bloqueado mientras falte una cuenta. El centro de costo
es opcional.

Al causar correctamente:

- se guardan las correcciones aplicadas a los ítems;
- la factura queda `procesado`;
- esa factura puede participar en el aprendizaje futuro.

Los intentos fallidos, duplicados no verificados y facturas pendientes no enseñan
al sistema.

## 9. Configuración

La pantalla “Mapa de cuentas” administrará solamente campos reales:

- NIT del proveedor;
- nombre del proveedor;
- cuenta de Alegra;
- centro de costo de Alegra;
- estado activo.

Se eliminan del formulario los campos de retenciones que el backend no admite.
Cuenta y centro se eligen desde el catálogo vigente de Alegra. La tabla mostrará
ambos nombres, la fuente y el estado.

## 10. Validaciones y seguridad contable

- Cuenta obligatoria al crear una regla.
- NIT normalizado a dígitos antes de buscar o guardar.
- IDs de cuenta y centro deben existir en el catálogo cargado al presentarlos al
  usuario; si un ID histórico ya no aparece, se muestra como valor registrado y
  requiere revisión.
- Una regla inactiva no se aplica.
- El aprendizaje automático no sobrescribe reglas manuales.
- La falta de clasificación nunca se reemplaza con una cuenta inventada.
- La causación conserva las comprobaciones actuales de duplicado e idempotencia.

## 11. Fuera de alcance

- Distribución porcentual o monetaria entre centros de costo.
- Múltiples cuentas para una misma factura.
- Clasificación por descripción de línea.
- IA, embeddings o modelos predictivos.
- Causación automática.
- Nuevas tablas, ORM o motor genérico de reglas.

## 12. Criterios de aceptación

- Una regla manual para Nitido precarga cuenta y centro en XML, PDF e IMAP.
- Una regla manual para Coordinadora precarga una única cuenta y un único centro.
- Una regla manual no cambia durante una recomputación automática.
- Tres facturas causadas con la misma pareja pueden producir una regla histórica.
- Facturas pendientes o fallidas no afectan el aprendizaje.
- Una factura causada con clasificación corregida guarda la corrección.
- Un proveedor ambiguo queda pendiente de clasificación manual.
- La pantalla de configuración crea y edita cuenta y centro sin enviar campos no
  soportados.
- La factura nunca se causa sin una acción explícita del operador.

