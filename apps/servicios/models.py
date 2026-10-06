from django.db import models


# =====================================================
# SERVICIO
# =====================================================

class Servicio(models.Model):

    id_servicio = models.AutoField(
        primary_key=True,
        db_column="id_servicio"
    )

    id_cliente = models.IntegerField(
        db_column="id_cliente"
    )

    codigo = models.CharField(
        max_length=50,
        db_column="codigo",
    )

    tipo_servicio = models.CharField(
        max_length=255,
        db_column="tipo_servicio"
    )

    estado = models.CharField(
        max_length=255,
        db_column="estado"
    )

    descripcion = models.TextField(
        db_column="descripcion",
        blank=True,
    )

    cantidad = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        db_column="cantidad",
    )

    facturable = models.BooleanField(
        db_column="facturable",
        default=True,
    )

    estado_facturacion = models.CharField(
        max_length=20,
        db_column="estado_facturacion",
        default="NO_APLICA",
    )

    tarifa_aplicada = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        db_column="tarifa_aplicada"
    )

    id_usuario_registro = models.UUIDField(
        db_column="id_usuario_registro"
    )

    id_usuario_ejecucion = models.UUIDField(
        db_column="id_usuario_ejecucion",
        null=True,
        blank=True,
    )

    fecha_servicio = models.DateTimeField(
        db_column="fecha_servicio"
    )

    fecha_ejecucion = models.DateTimeField(
        db_column="fecha_ejecucion",
        null=True,
        blank=True,
    )

    fecha_reporte = models.DateTimeField(
        db_column="fecha_reporte",
        null=True,
        blank=True,
    )

    observaciones = models.TextField(
        db_column="observaciones",
        blank=True,
    )


    class Meta:
        managed = False
        db_table = '"servicios"."servicio"'

        verbose_name = "Servicio"
        verbose_name_plural = "Servicios"


    def __str__(self):
        return self.tipo_servicio



# =====================================================
# REENCAJADO
# =====================================================

class Reencajado(models.Model):

    id_reencajado = models.AutoField(
        primary_key=True,
        db_column="id_reencajado"
    )

    id_servicio = models.IntegerField(
        db_column="id_servicio"
    )

    id_stock = models.IntegerField(
        db_column="id_stock"
    )

    cantidad_cajas_origen = models.IntegerField(
        db_column="cantidad_cajas_origen"
    )

    cantidad_cajas_destino = models.IntegerField(
        db_column="cantidad_cajas_destino"
    )


    class Meta:
        managed = False
        db_table = '"servicios"."reencajado"'

        verbose_name = "Reencajado"
        verbose_name_plural = "Reencajados"


    def __str__(self):
        return f"Reencajado {self.id_reencajado}"



# =====================================================
# REPALETIZADO
# =====================================================

class Repaletizado(models.Model):

    id_repaletizado = models.AutoField(
        primary_key=True,
        db_column="id_repaletizado"
    )

    id_servicio = models.IntegerField(
        db_column="id_servicio"
    )

    id_stock = models.IntegerField(
        db_column="id_stock"
    )

    id_pallet_origen = models.IntegerField(
        db_column="id_pallet_origen",
        null=True,
        blank=True,
    )

    id_pallet_destino = models.IntegerField(
        db_column="id_pallet_destino",
        null=True,
        blank=True,
    )

    cantidad_pallets = models.IntegerField(
        db_column="cantidad_pallets"
    )

    cliente_provee_pallet_destino = models.BooleanField(
        db_column="cliente_provee_pallet_destino",
        default=False,
    )

    tipo_pallet_destino = models.CharField(
        max_length=100,
        db_column="tipo_pallet_destino",
    )

    certificacion_destino = models.CharField(
        max_length=120,
        db_column="certificacion_destino",
        blank=True,
    )

    codigo_pallet_destino = models.CharField(
        max_length=255,
        db_column="codigo_pallet_destino",
        blank=True,
    )


    class Meta:
        managed = False
        db_table = '"servicios"."repaletizado"'

        verbose_name = "Repaletizado"
        verbose_name_plural = "Repaletizados"


    def __str__(self):
        return f"Repaletizado {self.id_repaletizado}"


# =====================================================
# EP-08 · OPERACIONES TÉCNICAS
# =====================================================


class EventoAuditoria(models.Model):
    id_evento = models.BigAutoField(primary_key=True)
    id_usuario = models.UUIDField(null=True, blank=True)
    usuario = models.CharField(max_length=255, blank=True)
    fecha = models.DateTimeField()
    modulo = models.CharField(max_length=80)
    accion = models.CharField(max_length=80)
    metodo = models.CharField(max_length=10)
    ruta = models.CharField(max_length=500)
    datos_afectados = models.JSONField(default=dict)
    estado_http = models.IntegerField()
    resultado = models.CharField(max_length=20)
    direccion_ip = models.CharField(max_length=64, blank=True)

    class Meta:
        managed = False
        db_table = '"tecnico"."evento_auditoria"'


class MetricaRendimiento(models.Model):
    id_metrica = models.BigAutoField(primary_key=True)
    fecha = models.DateTimeField()
    metodo = models.CharField(max_length=10)
    ruta = models.CharField(max_length=500)
    estado_http = models.IntegerField()
    duracion_ms = models.DecimalField(max_digits=12, decimal_places=3)
    memoria_mb = models.DecimalField(max_digits=12, decimal_places=3, null=True)
    consultas_db = models.IntegerField(default=0)
    error = models.TextField(blank=True)

    class Meta:
        managed = False
        db_table = '"tecnico"."metrica_rendimiento"'


class IncidenteSistema(models.Model):
    id_incidente = models.BigAutoField(primary_key=True)
    componente = models.CharField(max_length=120)
    estado = models.CharField(max_length=20)
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField(null=True, blank=True)
    detalle = models.TextField(blank=True)

    class Meta:
        managed = False
        db_table = '"tecnico"."incidente_sistema"'


class RespaldoBaseDatos(models.Model):
    id_respaldo = models.BigAutoField(primary_key=True)
    tipo = models.CharField(max_length=30)
    estado = models.CharField(max_length=30)
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField(null=True, blank=True)
    id_usuario = models.UUIDField(null=True, blank=True)
    usuario = models.CharField(max_length=255, blank=True)
    archivo = models.CharField(max_length=1000, blank=True)
    tamano_bytes = models.BigIntegerField(default=0)
    checksum_sha256 = models.CharField(max_length=64, blank=True)
    motor = models.CharField(max_length=80, blank=True)
    valido = models.BooleanField(default=False)
    resultado = models.TextField(blank=True)

    class Meta:
        managed = False
        db_table = '"tecnico"."respaldo_base_datos"'


class ProgramacionRespaldo(models.Model):
    id_programacion = models.AutoField(primary_key=True)
    activa = models.BooleanField(default=False)
    frecuencia_horas = models.IntegerField(default=24)
    retencion_dias = models.IntegerField(default=30)
    proxima_ejecucion = models.DateTimeField(null=True, blank=True)
    ultima_ejecucion = models.DateTimeField(null=True, blank=True)
    id_usuario_actualiza = models.UUIDField(null=True, blank=True)
    fecha_actualizacion = models.DateTimeField()

    class Meta:
        managed = False
        db_table = '"tecnico"."programacion_respaldo"'


class RestauracionBaseDatos(models.Model):
    id_restauracion = models.BigAutoField(primary_key=True)
    id_respaldo = models.BigIntegerField()
    estado = models.CharField(max_length=30)
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField(null=True, blank=True)
    id_usuario = models.UUIDField(null=True, blank=True)
    usuario = models.CharField(max_length=255, blank=True)
    resultado = models.TextField(blank=True)

    class Meta:
        managed = False
        db_table = '"tecnico"."restauracion_base_datos"'


class PoliticaConservacion(models.Model):
    id_politica = models.BigAutoField(primary_key=True)
    categoria = models.CharField(max_length=100, unique=True)
    periodo_dias = models.IntegerField()
    eliminacion_habilitada = models.BooleanField(default=False)
    protege_operaciones = models.BooleanField(default=True)
    descripcion = models.TextField(blank=True)
    id_usuario_actualiza = models.UUIDField(null=True, blank=True)
    fecha_actualizacion = models.DateTimeField()

    class Meta:
        managed = False
        db_table = '"tecnico"."politica_conservacion"'


class EjecucionIntegracion(models.Model):
    id_ejecucion = models.BigAutoField(primary_key=True)
    integracion = models.CharField(max_length=120)
    operacion = models.CharField(max_length=120)
    estado = models.CharField(max_length=20)
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField(null=True, blank=True)
    datos_procesados = models.IntegerField(default=0)
    detalle_error = models.TextField(blank=True)
    reintento_de = models.BigIntegerField(null=True, blank=True)
    intentos = models.IntegerField(default=1)
    id_usuario = models.UUIDField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = '"tecnico"."ejecucion_integracion"'


class VersionDespliegue(models.Model):
    id_version = models.BigAutoField(primary_key=True)
    version = models.CharField(max_length=80, unique=True)
    descripcion = models.TextField(blank=True)
    plan_reversion = models.TextField()
    aprobada = models.BooleanField(default=False)
    id_usuario_registro = models.UUIDField(null=True, blank=True)
    id_usuario_aprueba = models.UUIDField(null=True, blank=True)
    fecha_registro = models.DateTimeField()
    fecha_aprobacion = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = '"tecnico"."version_despliegue"'


class Despliegue(models.Model):
    id_despliegue = models.BigAutoField(primary_key=True)
    id_version = models.BigIntegerField()
    ambiente = models.CharField(max_length=40)
    estado = models.CharField(max_length=30)
    id_respaldo_previo = models.BigIntegerField(null=True, blank=True)
    version_anterior = models.CharField(max_length=80, blank=True)
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField(null=True, blank=True)
    id_usuario = models.UUIDField(null=True, blank=True)
    usuario = models.CharField(max_length=255, blank=True)
    resultado = models.TextField(blank=True)

    class Meta:
        managed = False
        db_table = '"tecnico"."despliegue"'
