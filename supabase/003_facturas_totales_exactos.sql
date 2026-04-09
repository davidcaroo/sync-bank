-- Exactitud monetaria de facturas DIAN.
-- Ejecutar en Supabase SQL editor antes de habilitar persistencia extendida.

alter table if exists public.facturas
add column if not exists cargos_adicionales double precision default 0,
add column if not exists anticipos double precision default 0,
add column if not exists redondeo double precision default 0,
add column if not exists total_calculado double precision,
add column if not exists diferencia_centavos integer default 0,
add column if not exists validacion_total text,
add column if not exists parsed_version integer default 1,
add column if not exists calculo_exacto boolean default false;

create index if not exists facturas_validacion_total_idx
on public.facturas (validacion_total)
where validacion_total is not null;

create index if not exists facturas_calculo_exacto_idx
on public.facturas (calculo_exacto, created_at desc);
