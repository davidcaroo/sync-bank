-- Optional schema update to persist supplier name from XML in config_cuentas.
-- Run in Supabase SQL editor before expecting automatic updates.

alter table if exists public.config_cuentas
add column if not exists nombre_proveedor text;
