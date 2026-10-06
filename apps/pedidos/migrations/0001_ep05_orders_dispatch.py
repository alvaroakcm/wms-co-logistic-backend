from django.db import migrations


FORWARD_SQL = """
ALTER TABLE pedidos.pedido_detalle
    ADD COLUMN IF NOT EXISTS id_lote integer;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'pedido_detalle_id_lote_fkey'
          AND conrelid = 'pedidos.pedido_detalle'::regclass
    ) THEN
        ALTER TABLE pedidos.pedido_detalle
            ADD CONSTRAINT pedido_detalle_id_lote_fkey
            FOREIGN KEY (id_lote) REFERENCES inventario.lote(id_lote)
            ON DELETE RESTRICT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'picking_pedido_salida_key'
          AND conrelid = 'pedidos.picking'::regclass
    ) THEN
        ALTER TABLE pedidos.picking
            ADD CONSTRAINT picking_pedido_salida_key
            UNIQUE (id_pedido_salida);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'despacho_pedido_salida_key'
          AND conrelid = 'pedidos.despacho'::regclass
    ) THEN
        ALTER TABLE pedidos.despacho
            ADD CONSTRAINT despacho_pedido_salida_key
            UNIQUE (id_pedido_salida);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_pedido_salida_estado_fecha
    ON pedidos.pedido_salida (estado, fecha_programada, fecha_registro DESC);
CREATE INDEX IF NOT EXISTS idx_pedido_detalle_producto_lote
    ON pedidos.pedido_detalle (id_producto, id_lote);
CREATE INDEX IF NOT EXISTS idx_reserva_pedido_estado
    ON inventario.reserva (id_pedido_detalle, estado);
"""


REVERSE_SQL = """
DROP INDEX IF EXISTS inventario.idx_reserva_pedido_estado;
DROP INDEX IF EXISTS pedidos.idx_pedido_detalle_producto_lote;
DROP INDEX IF EXISTS pedidos.idx_pedido_salida_estado_fecha;
ALTER TABLE pedidos.despacho DROP CONSTRAINT IF EXISTS despacho_pedido_salida_key;
ALTER TABLE pedidos.picking DROP CONSTRAINT IF EXISTS picking_pedido_salida_key;
ALTER TABLE pedidos.pedido_detalle
    DROP CONSTRAINT IF EXISTS pedido_detalle_id_lote_fkey,
    DROP COLUMN IF EXISTS id_lote;
"""


class Migration(migrations.Migration):
    dependencies = []

    operations = [migrations.RunSQL(FORWARD_SQL, REVERSE_SQL)]
