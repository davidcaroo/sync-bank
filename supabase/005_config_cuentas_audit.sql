-- Create audit table for config_cuentas mappings
CREATE TABLE IF NOT EXISTS config_cuentas_audit (
    id BIGSERIAL PRIMARY KEY,
    nit_proveedor TEXT NOT NULL,
    id_cuenta_alegra TEXT NOT NULL,
    id_centro_costo_alegra TEXT NULL,
    confianza NUMERIC NULL,
    source TEXT NULL,
    "user" TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_config_cuentas_audit_nit ON config_cuentas_audit (nit_proveedor);
CREATE INDEX IF NOT EXISTS idx_config_cuentas_audit_created ON config_cuentas_audit (created_at);
