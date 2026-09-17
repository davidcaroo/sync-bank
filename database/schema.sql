create table if not exists public.facturas (
    id uuid primary key default gen_random_uuid(),
    cufe text,
    numero_factura text,
    fecha_emision timestamptz,
    fecha_vencimiento timestamptz,
    nit_proveedor text,
    nombre_proveedor text,
    nit_receptor text,
    subtotal numeric(20, 2) not null default 0,
    iva numeric(20, 2) not null default 0,
    rete_fuente numeric(20, 2) not null default 0,
    rete_ica numeric(20, 2) not null default 0,
    rete_iva numeric(20, 2) not null default 0,
    total numeric(20, 2) not null default 0,
    moneda text not null default 'COP',
    xml_raw text,
    estado text not null default 'pendiente',
    cargos_adicionales numeric(20, 2) not null default 0,
    anticipos numeric(20, 2) not null default 0,
    redondeo numeric(20, 2) not null default 0,
    total_calculado numeric(20, 2),
    diferencia_centavos integer not null default 0,
    validacion_total text,
    parsed_version integer not null default 1,
    calculo_exacto boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create unique index if not exists facturas_cufe_unique_idx
on public.facturas (cufe)
where cufe is not null and btrim(cufe) <> '';
create index if not exists facturas_created_at_idx on public.facturas (created_at desc);
create index if not exists facturas_estado_idx on public.facturas (estado);
create index if not exists facturas_nit_proveedor_idx on public.facturas (nit_proveedor);

create table if not exists public.items_factura (
    id uuid primary key default gen_random_uuid(),
    factura_id uuid not null references public.facturas(id) on delete cascade,
    descripcion text not null default '',
    cantidad numeric(20, 6) not null default 0,
    precio_unitario numeric(20, 2) not null default 0,
    descuento numeric(20, 2) not null default 0,
    iva_porcentaje numeric(8, 4) not null default 19,
    total_linea numeric(20, 2) not null default 0,
    cuenta_contable_alegra text,
    centro_costo_alegra text,
    prefill_source text,
    confidence numeric(8, 6),
    created_at timestamptz not null default now()
);
create index if not exists items_factura_factura_id_idx on public.items_factura (factura_id);

create table if not exists public.causaciones (
    id uuid primary key default gen_random_uuid(),
    factura_id uuid not null references public.facturas(id) on delete cascade,
    alegra_bill_id text,
    alegra_response jsonb,
    estado text not null,
    intentos integer not null default 1,
    error_msg text,
    created_at timestamptz not null default now()
);
create index if not exists causaciones_factura_estado_idx
on public.causaciones (factura_id, estado, created_at desc);

create table if not exists public.config_cuentas (
    id uuid primary key default gen_random_uuid(),
    nit_proveedor text not null unique,
    nombre_proveedor text,
    id_cuenta_alegra text not null,
    id_centro_costo_alegra text,
    confianza numeric(8, 6),
    activo boolean not null default true,
    source text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.config_cuentas_audit (
    id bigserial primary key,
    nit_proveedor text not null,
    id_cuenta_alegra text not null,
    id_centro_costo_alegra text,
    confianza numeric(8, 6),
    source text,
    "user" text,
    created_at timestamptz not null default now()
);
create index if not exists config_cuentas_audit_nit_idx on public.config_cuentas_audit (nit_proveedor);

create table if not exists public.logs_email (
    id uuid primary key default gen_random_uuid(),
    mensaje_id text not null unique,
    remitente text,
    asunto text,
    estado text not null,
    attachments_encontrados integer not null default 0,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index if not exists logs_email_created_at_idx on public.logs_email (created_at desc);
create index if not exists logs_email_estado_idx on public.logs_email (estado);

create table if not exists public.documentos_pendientes (
    id uuid primary key default gen_random_uuid(),
    message_id text not null,
    attachment_sha256 text not null,
    file_name text not null,
    page_start integer not null,
    page_end integer not null,
    raw_text text not null,
    candidate jsonb not null,
    missing_fields jsonb not null default '[]'::jsonb,
    warnings jsonb not null default '[]'::jsonb,
    estado text not null default 'requiere_revision',
    factura_id uuid references public.facturas(id),
    created_at timestamptz not null default now(),
    resolved_at timestamptz,
    unique (attachment_sha256, page_start, page_end)
);
create index if not exists documentos_pendientes_estado_idx
on public.documentos_pendientes (estado, created_at desc);
