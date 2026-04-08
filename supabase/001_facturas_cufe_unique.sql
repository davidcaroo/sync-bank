-- Enforce idempotency at DB level: one invoice per CUFE (ignoring null/blank values).
-- Run this script in Supabase SQL editor.

create unique index if not exists facturas_cufe_unique_idx
on public.facturas (cufe)
where cufe is not null and btrim(cufe) <> '';
