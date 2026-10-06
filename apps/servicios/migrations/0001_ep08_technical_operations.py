from django.db import migrations


FORWARD_SQL = """
CREATE SCHEMA IF NOT EXISTS tecnico;

CREATE TABLE IF NOT EXISTS tecnico.evento_auditoria (
    id_evento bigserial PRIMARY KEY,
    id_usuario uuid NULL,
    usuario varchar(255) NOT NULL DEFAULT '',
    fecha timestamptz NOT NULL DEFAULT now(),
    modulo varchar(80) NOT NULL,
    accion varchar(80) NOT NULL,
    metodo varchar(10) NOT NULL,
    ruta varchar(500) NOT NULL,
    datos_afectados jsonb NOT NULL DEFAULT '{}'::jsonb,
    estado_http integer NOT NULL,
    resultado varchar(20) NOT NULL,
    direccion_ip varchar(64) NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS tecnico.metrica_rendimiento (
    id_metrica bigserial PRIMARY KEY,
    fecha timestamptz NOT NULL DEFAULT now(),
    metodo varchar(10) NOT NULL,
    ruta varchar(500) NOT NULL,
    estado_http integer NOT NULL,
    duracion_ms numeric(12,3) NOT NULL,
    memoria_mb numeric(12,3) NULL,
    consultas_db integer NOT NULL DEFAULT 0,
    error text NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS tecnico.incidente_sistema (
    id_incidente bigserial PRIMARY KEY,
    componente varchar(120) NOT NULL,
    estado varchar(20) NOT NULL,
    fecha_inicio timestamptz NOT NULL DEFAULT now(),
    fecha_fin timestamptz NULL,
    detalle text NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS tecnico.respaldo_base_datos (
    id_respaldo bigserial PRIMARY KEY,
    tipo varchar(30) NOT NULL,
    estado varchar(30) NOT NULL,
    fecha_inicio timestamptz NOT NULL DEFAULT now(),
    fecha_fin timestamptz NULL,
    id_usuario uuid NULL,
    usuario varchar(255) NOT NULL DEFAULT '',
    archivo varchar(1000) NOT NULL DEFAULT '',
    tamano_bytes bigint NOT NULL DEFAULT 0,
    checksum_sha256 varchar(64) NOT NULL DEFAULT '',
    motor varchar(80) NOT NULL DEFAULT '',
    valido boolean NOT NULL DEFAULT false,
    resultado text NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS tecnico.programacion_respaldo (
    id_programacion serial PRIMARY KEY,
    activa boolean NOT NULL DEFAULT false,
    frecuencia_horas integer NOT NULL DEFAULT 24 CHECK (frecuencia_horas BETWEEN 1 AND 8760),
    retencion_dias integer NOT NULL DEFAULT 30 CHECK (retencion_dias BETWEEN 1 AND 3650),
    proxima_ejecucion timestamptz NULL,
    ultima_ejecucion timestamptz NULL,
    id_usuario_actualiza uuid NULL,
    fecha_actualizacion timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tecnico.restauracion_base_datos (
    id_restauracion bigserial PRIMARY KEY,
    id_respaldo bigint NOT NULL REFERENCES tecnico.respaldo_base_datos(id_respaldo) ON DELETE RESTRICT,
    estado varchar(30) NOT NULL,
    fecha_inicio timestamptz NOT NULL DEFAULT now(),
    fecha_fin timestamptz NULL,
    id_usuario uuid NULL,
    usuario varchar(255) NOT NULL DEFAULT '',
    resultado text NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS tecnico.politica_conservacion (
    id_politica bigserial PRIMARY KEY,
    categoria varchar(100) NOT NULL UNIQUE,
    periodo_dias integer NOT NULL CHECK (periodo_dias BETWEEN 1 AND 36500),
    eliminacion_habilitada boolean NOT NULL DEFAULT false,
    protege_operaciones boolean NOT NULL DEFAULT true,
    descripcion text NOT NULL DEFAULT '',
    id_usuario_actualiza uuid NULL,
    fecha_actualizacion timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tecnico.ejecucion_integracion (
    id_ejecucion bigserial PRIMARY KEY,
    integracion varchar(120) NOT NULL,
    operacion varchar(120) NOT NULL,
    estado varchar(20) NOT NULL,
    fecha_inicio timestamptz NOT NULL DEFAULT now(),
    fecha_fin timestamptz NULL,
    datos_procesados integer NOT NULL DEFAULT 0,
    detalle_error text NOT NULL DEFAULT '',
    reintento_de bigint NULL REFERENCES tecnico.ejecucion_integracion(id_ejecucion) ON DELETE SET NULL,
    intentos integer NOT NULL DEFAULT 1,
    id_usuario uuid NULL
);

CREATE TABLE IF NOT EXISTS tecnico.version_despliegue (
    id_version bigserial PRIMARY KEY,
    version varchar(80) NOT NULL UNIQUE,
    descripcion text NOT NULL DEFAULT '',
    plan_reversion text NOT NULL,
    aprobada boolean NOT NULL DEFAULT false,
    id_usuario_registro uuid NULL,
    id_usuario_aprueba uuid NULL,
    fecha_registro timestamptz NOT NULL DEFAULT now(),
    fecha_aprobacion timestamptz NULL
);

CREATE TABLE IF NOT EXISTS tecnico.despliegue (
    id_despliegue bigserial PRIMARY KEY,
    id_version bigint NOT NULL REFERENCES tecnico.version_despliegue(id_version) ON DELETE RESTRICT,
    ambiente varchar(40) NOT NULL,
    estado varchar(30) NOT NULL,
    id_respaldo_previo bigint NULL REFERENCES tecnico.respaldo_base_datos(id_respaldo) ON DELETE RESTRICT,
    version_anterior varchar(80) NOT NULL DEFAULT '',
    fecha_inicio timestamptz NOT NULL DEFAULT now(),
    fecha_fin timestamptz NULL,
    id_usuario uuid NULL,
    usuario varchar(255) NOT NULL DEFAULT '',
    resultado text NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_auditoria_fecha ON tecnico.evento_auditoria (fecha DESC);
CREATE INDEX IF NOT EXISTS idx_auditoria_filtros ON tecnico.evento_auditoria (modulo, accion, resultado);
CREATE INDEX IF NOT EXISTS idx_rendimiento_fecha ON tecnico.metrica_rendimiento (fecha DESC);
CREATE INDEX IF NOT EXISTS idx_respaldo_fecha ON tecnico.respaldo_base_datos (fecha_inicio DESC);
CREATE INDEX IF NOT EXISTS idx_integracion_fecha ON tecnico.ejecucion_integracion (fecha_inicio DESC);
"""


REVERSE_SQL = """
DROP SCHEMA IF EXISTS tecnico CASCADE;
"""


class Migration(migrations.Migration):
    dependencies = []

    operations = [migrations.RunSQL(FORWARD_SQL, REVERSE_SQL)]
