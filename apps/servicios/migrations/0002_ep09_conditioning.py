from django.db import migrations


FORWARD_SQL = """
ALTER TABLE servicios.servicio
    ADD COLUMN IF NOT EXISTS codigo varchar(50),
    ADD COLUMN IF NOT EXISTS descripcion text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS cantidad numeric(12,4) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS facturable boolean NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS estado_facturacion varchar(20) NOT NULL DEFAULT 'NO_APLICA',
    ADD COLUMN IF NOT EXISTS id_usuario_ejecucion uuid NULL,
    ADD COLUMN IF NOT EXISTS fecha_ejecucion timestamptz NULL,
    ADD COLUMN IF NOT EXISTS fecha_reporte timestamptz NULL,
    ADD COLUMN IF NOT EXISTS observaciones text NOT NULL DEFAULT '';

UPDATE servicios.servicio
SET codigo = 'SRV-' || lpad(id_servicio::text, 6, '0')
WHERE codigo IS NULL OR btrim(codigo) = '';

ALTER TABLE servicios.servicio
    ALTER COLUMN codigo SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'servicio_codigo_key'
          AND conrelid = 'servicios.servicio'::regclass
    ) THEN
        ALTER TABLE servicios.servicio
            ADD CONSTRAINT servicio_codigo_key UNIQUE (codigo);
    END IF;
END $$;

ALTER TABLE servicios.repaletizado
    ALTER COLUMN id_pallet_origen DROP NOT NULL,
    ALTER COLUMN id_pallet_destino DROP NOT NULL,
    ADD COLUMN IF NOT EXISTS cliente_provee_pallet_destino boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS tipo_pallet_destino varchar(100) NOT NULL DEFAULT 'Estándar de exportación',
    ADD COLUMN IF NOT EXISTS certificacion_destino varchar(120) NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS codigo_pallet_destino varchar(255) NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_servicio_acondicionamiento
    ON servicios.servicio (tipo_servicio, estado, fecha_servicio DESC);
CREATE INDEX IF NOT EXISTS idx_servicio_facturacion
    ON servicios.servicio (facturable, estado_facturacion, fecha_ejecucion DESC);
"""


REVERSE_SQL = """
DROP INDEX IF EXISTS servicios.idx_servicio_facturacion;
DROP INDEX IF EXISTS servicios.idx_servicio_acondicionamiento;
ALTER TABLE servicios.repaletizado
    DROP COLUMN IF EXISTS codigo_pallet_destino,
    DROP COLUMN IF EXISTS certificacion_destino,
    DROP COLUMN IF EXISTS tipo_pallet_destino,
    DROP COLUMN IF EXISTS cliente_provee_pallet_destino;
ALTER TABLE servicios.servicio DROP CONSTRAINT IF EXISTS servicio_codigo_key;
ALTER TABLE servicios.servicio
    DROP COLUMN IF EXISTS observaciones,
    DROP COLUMN IF EXISTS fecha_reporte,
    DROP COLUMN IF EXISTS fecha_ejecucion,
    DROP COLUMN IF EXISTS id_usuario_ejecucion,
    DROP COLUMN IF EXISTS estado_facturacion,
    DROP COLUMN IF EXISTS facturable,
    DROP COLUMN IF EXISTS cantidad,
    DROP COLUMN IF EXISTS descripcion,
    DROP COLUMN IF EXISTS codigo;
"""


class Migration(migrations.Migration):
    dependencies = [("servicios", "0001_ep08_technical_operations")]

    operations = [migrations.RunSQL(FORWARD_SQL, REVERSE_SQL)]
