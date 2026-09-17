select 'facturas' as tabla, count(*) as filas from public.facturas
union all select 'items_factura', count(*) from public.items_factura
union all select 'causaciones', count(*) from public.causaciones
union all select 'config_cuentas', count(*) from public.config_cuentas
union all select 'config_cuentas_audit', count(*) from public.config_cuentas_audit
union all select 'logs_email', count(*) from public.logs_email
order by tabla;

select
  count(*) filter (where cufe is not null and btrim(cufe) <> '') as cufes,
  count(distinct cufe) filter (where cufe is not null and btrim(cufe) <> '') as cufes_unicos,
  coalesce(sum(total::numeric), 0) as total_facturas
from public.facturas;
