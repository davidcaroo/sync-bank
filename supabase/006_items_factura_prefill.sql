-- Add prefill flags for items_factura
ALTER TABLE items_factura
    ADD COLUMN IF NOT EXISTS prefill_source TEXT NULL,
    ADD COLUMN IF NOT EXISTS confidence NUMERIC NULL;
