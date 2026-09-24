from repositories.database import transaction

# schema.sql is applied manually, so additive changes must also reach existing
# databases on startup. Every statement here must be idempotent.
UPGRADES = (
    "alter table public.config_cuentas "
    "add column if not exists auto_causar boolean not null default false",
    "alter table public.config_cuentas_audit "
    "add column if not exists auto_causar boolean not null default false",
    """
    create table if not exists public.sync_jobs (
        id uuid primary key default gen_random_uuid(),
        job_type text not null default 'email_sync',
        status text not null default 'pending'
            check (status in ('pending', 'running', 'succeeded', 'failed')),
        progress jsonb not null default '{}'::jsonb,
        result jsonb,
        attempts integer not null default 0,
        max_attempts integer not null default 3,
        error_message text,
        requested_by text not null default 'manual',
        created_at timestamptz not null default now(),
        started_at timestamptz,
        finished_at timestamptz,
        updated_at timestamptz not null default now()
    )
    """,
    "create unique index if not exists sync_jobs_one_active_idx "
    "on public.sync_jobs (job_type) where status in ('pending', 'running')",
    "create index if not exists sync_jobs_created_at_idx "
    "on public.sync_jobs (created_at desc)",
)


def apply_schema_upgrades() -> None:
    with transaction() as conn:
        for statement in UPGRADES:
            conn.execute(statement)
