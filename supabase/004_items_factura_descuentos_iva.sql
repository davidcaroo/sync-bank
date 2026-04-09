-- Asegura columnas de detalle monetario por item para auditoria de exactitud.
-- Ejecutar en Supabase SQL editor.

alter table if exists public.items_factura
add column if not exists descuento double precision default 0,
add column if not exists iva_porcentaje double precision default 19;
