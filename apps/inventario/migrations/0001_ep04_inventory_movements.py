from django.db import migrations


FORWARD_SQL = """
ALTER TABLE inventario.movimiento
    ADD COLUMN IF NOT EXISTS estado varchar(20) NOT NULL DEFAULT 'PENDIENTE';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_movimiento_estado'
          AND conrelid = 'inventario.movimiento'::regclass
    ) THEN
        ALTER TABLE inventario.movimiento
            ADD CONSTRAINT chk_movimiento_estado
            CHECK (estado IN ('PENDIENTE', 'CONFIRMADO', 'CANCELADO'));
    END IF;
END $$;

ALTER TABLE inventario.movimiento_detalle
    ADD COLUMN IF NOT EXISTS id_ubicacion_origen integer;

UPDATE inventario.movimiento_detalle detalle
SET id_ubicacion_origen = stock.id_ubicacion
FROM inventario.stock stock
WHERE detalle.id_stock_origen = stock.id_stock
  AND detalle.id_ubicacion_origen IS NULL;

ALTER TABLE inventario.movimiento_detalle
    ALTER COLUMN id_ubicacion_origen SET NOT NULL;

ALTER TABLE inventario.movimiento_detalle
    ADD COLUMN IF NOT EXISTS id_stock_destino integer;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'mov_detalle_ubicacion_origen_fkey'
          AND conrelid = 'inventario.movimiento_detalle'::regclass
    ) THEN
        ALTER TABLE inventario.movimiento_detalle
            ADD CONSTRAINT mov_detalle_ubicacion_origen_fkey
            FOREIGN KEY (id_ubicacion_origen)
            REFERENCES maestros.ubicacion(id_ubicacion);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'mov_detalle_stock_destino_fkey'
          AND conrelid = 'inventario.movimiento_detalle'::regclass
    ) THEN
        ALTER TABLE inventario.movimiento_detalle
            ADD CONSTRAINT mov_detalle_stock_destino_fkey
            FOREIGN KEY (id_stock_destino)
            REFERENCES inventario.stock(id_stock);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_movimiento_estado_fecha
    ON inventario.movimiento (estado, fecha_registro DESC);
CREATE INDEX IF NOT EXISTS idx_movimiento_detalle_origen_destino
    ON inventario.movimiento_detalle (id_ubicacion_origen, id_ubicacion_destino);
CREATE INDEX IF NOT EXISTS idx_stock_busqueda_ep04
    ON inventario.stock (id_producto, id_ubicacion, estado_stock);
CREATE INDEX IF NOT EXISTS idx_lote_vencimiento_ep04
    ON inventario.lote (fecha_vencimiento)
    WHERE fecha_vencimiento IS NOT NULL;
"""


REVERSE_SQL = """
DROP INDEX IF EXISTS inventario.idx_lote_vencimiento_ep04;
DROP INDEX IF EXISTS inventario.idx_stock_busqueda_ep04;
DROP INDEX IF EXISTS inventario.idx_movimiento_detalle_origen_destino;
DROP INDEX IF EXISTS inventario.idx_movimiento_estado_fecha;
ALTER TABLE inventario.movimiento_detalle
    DROP CONSTRAINT IF EXISTS mov_detalle_stock_destino_fkey,
    DROP CONSTRAINT IF EXISTS mov_detalle_ubicacion_origen_fkey,
    DROP COLUMN IF EXISTS id_stock_destino,
    DROP COLUMN IF EXISTS id_ubicacion_origen;
ALTER TABLE inventario.movimiento
    DROP CONSTRAINT IF EXISTS chk_movimiento_estado,
    DROP COLUMN IF EXISTS estado;
"""


class Migration(migrations.Migration):
    dependencies = []

    operations = [
        migrations.RunSQL(FORWARD_SQL, REVERSE_SQL),
    ]
