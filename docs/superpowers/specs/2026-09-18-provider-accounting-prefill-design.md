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

Por defecto, la factura permanece en estado `pendiente`. Un operador abre la
factura, revisa la clasificación y presiona **Causar en Alegra**. Sólo los
proveedores autorizados explícitamente podrán autocausarse desde XML DIAN.

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
8. La acción final de causar es humana por defecto.
9. La autocausación sólo se habilita manualmente por NIT y únicamente para XML
   DIAN válido recibido por IMAP.
10. El PDF adjunto o contenido en el ZIP es soporte; el XML es la fuente de verdad.

## 3. Casos esperados

### Nitido Car Wash

Una regla activa relaciona su NIT con su cuenta y centro de costo. Cada nueva
factura recibe ambos valores automáticamente y queda pendiente de confirmación.

### Coordinadora

Una regla activa relaciona su NIT con una cuenta y un único centro de costo. El
100 % de la factura se causa con esa clasificación.

### Peaje DEVISAB

Las facturas de ejemplo son emitidas por **DEVISAB S.A.S., NIT 901209021**. El
NIT `901533793` que aparece dentro de la descripción pertenece a la unión de
peajes y no se usa para seleccionar la regla contable.

Cuando una regla manual activa para el NIT emisor tenga habilitada la
autocausación, Sync-bank podrá causar automáticamente la factura sólo si llega
por IMAP como XML DIAN válido, incluso cuando el XML y el PDF vengan dentro de un
ZIP. La cuenta y el centro provienen de la regla; valor, fecha, placa y
descripción provienen del XML de cada factura.

La descripción de la partida se conserva literalmente. Para la muestra:

```text
Paso por Peaje GAMBOTE por el valor de 13.900 con la placa SMN255, el dia
14-09-26 09:12. UT PEAJES NACIONALES NIT:901533793
```

La muestra tiene subtotal y total de COP 13.900, IVA 0 % y un solo ítem. El
parser no puede asignar IVA 19 % por defecto cuando la línea no trae un nodo de
impuesto.

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

No se necesitan tablas nuevas. Se reutiliza `config_cuentas`, conservando sus
campos actuales y añadiendo solamente `auto_causar`:

- `nit_proveedor`;
- `nombre_proveedor`;
- `id_cuenta_alegra`;
- `id_centro_costo_alegra`;
- `confianza`;
- `activo`;
- `source`;
- `auto_causar`, desactivado por defecto.

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
es opcional, salvo en una regla de autocausación, donde cuenta y centro deben
estar configurados.

Al causar correctamente:

- se guardan las correcciones aplicadas a los ítems;
- la factura queda `procesado`;
- esa factura puede participar en el aprendizaje futuro.

Los intentos fallidos, duplicados no verificados y facturas pendientes no enseñan
al sistema.

## 8.1 Autocausación autorizada

La autocausación es una excepción opt-in en `config_cuentas`, nunca una inferencia
histórica. Para ejecutarla deben cumplirse todas estas condiciones:

1. origen `IMAP + XML`; nunca PDF/OCR ni carga manual;
2. CUFE real y número de factura presentes;
3. NIT emisor normalizado igual al de una regla manual activa;
4. `auto_causar = true` en esa regla;
5. cuenta y centro de costo configurados;
6. moneda COP, total positivo e ítems presentes;
7. suma de líneas, subtotal, IVA, retenciones y total coherentes a un centavo;
8. porcentaje de IVA de cada línea leído del XML; ausencia de impuesto equivale
   a 0 %, no a 19 %;
9. CUFE no existente y ausencia de causación exitosa previa.

Si alguna condición no se cumple, la factura queda `pendiente` con el motivo y no
se envía a Alegra. Si Alegra rechaza la autocausación, la factura vuelve a
`pendiente` para revisión humana; el correo no se reprocesará ni se crearán
duplicados.

La descripción del ítem se envía en `purchases.categories[].observations` y se
mantiene también en las observaciones generales ya existentes.

## 9. Configuración

La pantalla “Mapa de cuentas” administrará solamente campos reales:

- NIT del proveedor;
- nombre del proveedor;
- cuenta de Alegra;
- centro de costo de Alegra;
- autocausación desde XML, desactivada por defecto;
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
- El aprendizaje automático nunca habilita `auto_causar`.
- Cambiar cuenta, centro o NIT desactiva la autocausación hasta que el operador la
  habilite nuevamente.
- La falta de clasificación nunca se reemplaza con una cuenta inventada.
- La causación conserva las comprobaciones actuales de duplicado e idempotencia.

## 11. Fuera de alcance

- Distribución porcentual o monetaria entre centros de costo.
- Múltiples cuentas para una misma factura.
- Clasificación por descripción de línea.
- IA, embeddings o modelos predictivos.
- Causación automática general o aprendida desde historial.
- Autocausación desde PDF, OCR, carga manual o proveedor no autorizado.
- Nuevas tablas, ORM o motor genérico de reglas.

## 12. Criterios de aceptación

- Una regla manual para Nitido precarga cuenta y centro en XML, PDF e IMAP.
- Una regla manual para Coordinadora precarga una única cuenta y un único centro.
- Una regla manual no cambia durante una recomputación automática.
- Tres facturas causadas con la misma pareja pueden producir una regla histórica.
- Facturas pendientes o fallidas no afectan el aprendizaje.
- Una factura causada con clasificación corregida guarda la corrección.
- Un proveedor ambiguo queda pendiente de clasificación manual.
- El ZIP de la muestra procesa el XML DIAN y no intenta interpretar su PDF como
  fuente contable.
- La factura de peaje conserva la descripción del XML y se envía con IVA 0 %.
- Sólo una regla manual activa con `auto_causar = true` puede iniciar una
  causación desde IMAP.
- Un fallo de autocausación deja la factura pendiente y visible para revisión.
- La pantalla de configuración crea y edita cuenta y centro sin enviar campos no
  soportados.
- Toda factura no autorizada para autocausación requiere una acción explícita del
  operador.
