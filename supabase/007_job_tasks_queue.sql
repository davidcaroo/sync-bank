-- Queue jobs for background workers (Dramatiq + Redis)
create table if not exists public.job_tasks (
    id uuid primary key,
    job_type text not null,
    factura_id uuid not null references public.facturas(id) on delete cascade,
    status text not null check (status in ('queued', 'running', 'success', 'failed')),
    payload jsonb not null default '{}'::jsonb,
    result jsonb,
    error text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    started_at timestamptz,
    finished_at timestamptz
);

create index if not exists idx_job_tasks_factura_status on public.job_tasks (factura_id, status);
create index if not exists idx_job_tasks_job_type_status on public.job_tasks (job_type, status);
