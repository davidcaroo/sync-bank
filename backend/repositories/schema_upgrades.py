from repositories.database import transaction

# schema.sql is applied manually, so additive changes must also reach existing
# databases on startup. Every statement here must be idempotent.
UPGRADES = (
    "alter table public.config_cuentas "
    "add column if not exists auto_causar boolean not null default false",
    "alter table public.config_cuentas_audit "
    "add column if not exists auto_causar boolean not null default false",
)


def apply_schema_upgrades() -> None:
    with transaction() as conn:
        for statement in UPGRADES:
            conn.execute(statement)
