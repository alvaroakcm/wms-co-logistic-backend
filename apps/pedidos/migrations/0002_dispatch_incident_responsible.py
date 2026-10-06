from django.db import migrations


FORWARD_SQL = """
ALTER TABLE pedidos.incidencia_despacho
    ADD COLUMN IF NOT EXISTS id_usuario_registro uuid;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'incidencia_despacho_usuario_fkey'
          AND conrelid = 'pedidos.incidencia_despacho'::regclass
    ) THEN
        ALTER TABLE pedidos.incidencia_despacho
            ADD CONSTRAINT incidencia_despacho_usuario_fkey
            FOREIGN KEY (id_usuario_registro) REFERENCES usuarios.usuario(id_usuario)
            ON DELETE RESTRICT;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_incidencia_despacho_fecha_tipo
    ON pedidos.incidencia_despacho (fecha_registro DESC, tipo);
"""


REVERSE_SQL = """
DROP INDEX IF EXISTS pedidos.idx_incidencia_despacho_fecha_tipo;
ALTER TABLE pedidos.incidencia_despacho
    DROP CONSTRAINT IF EXISTS incidencia_despacho_usuario_fkey,
    DROP COLUMN IF EXISTS id_usuario_registro;
"""


class Migration(migrations.Migration):
    dependencies = [("pedidos", "0001_ep05_orders_dispatch")]

    operations = [migrations.RunSQL(FORWARD_SQL, REVERSE_SQL)]
