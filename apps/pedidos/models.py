from django.db import models


# =====================================================
# PEDIDO SALIDA
# =====================================================

class PedidoSalida(models.Model):

    id_pedido_salida = models.AutoField(
        primary_key=True,
        db_column="id_pedido_salida"
    )

    id_cliente = models.IntegerField(
        db_column="id_cliente"
    )

    codigo_documento = models.CharField(
        max_length=255,
        db_column="codigo_documento"
    )

    fecha_programada = models.DateField(
        db_column="fecha_programada"
    )

    fecha_despacho = models.DateTimeField(
        db_column="fecha_despacho",
        null=True,
        blank=True
    )

    transporte_placa = models.CharField(
        max_length=255,
        db_column="transporte_placa",
        null=True,
        blank=True
    )

    transporte_conductor = models.CharField(
        max_length=255,
        db_column="transporte_conductor",
        null=True,
        blank=True
    )

    estado = models.CharField(
        max_length=255,
        db_column="estado"
    )

    id_usuario_registro = models.UUIDField(
        db_column="id_usuario_registro"
    )

    fecha_registro = models.DateTimeField(
        db_column="fecha_registro"
    )

    fecha_actualizacion = models.DateTimeField(
        db_column="fecha_actualizacion"
    )


    class Meta:
        managed = False
        db_table = '"pedidos"."pedido_salida"'

        verbose_name = "Pedido Salida"
        verbose_name_plural = "Pedidos Salida"


    def __str__(self):
        return self.codigo_documento



# =====================================================
# PEDIDO DETALLE
# =====================================================

class PedidoDetalle(models.Model):

    id_pedido_detalle = models.AutoField(
        primary_key=True,
        db_column="id_pedido_detalle"
    )

    id_pedido_salida = models.IntegerField(
        db_column="id_pedido_salida"
    )

    id_producto = models.IntegerField(
        db_column="id_producto"
    )

    cantidad_solicitada = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        db_column="cantidad_solicitada"
    )

    cantidad_despachada = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        db_column="cantidad_despachada"
    )

    id_unidad_medida = models.IntegerField(
        db_column="id_unidad_medida"
    )


    class Meta:
        managed = False
        db_table = '"pedidos"."pedido_detalle"'

        verbose_name = "Detalle Pedido"
        verbose_name_plural = "Detalles Pedido"


    def __str__(self):
        return f"Detalle {self.id_pedido_detalle}"

# =====================================================
# PICKING
# =====================================================

class Picking(models.Model):

    id_picking = models.AutoField(
        primary_key=True,
        db_column="id_picking"
    )

    id_pedido_salida = models.IntegerField(
        db_column="id_pedido_salida"
    )

    id_usuario_asignado = models.UUIDField(
        db_column="id_usuario_asignado"
    )

    estado = models.CharField(
        max_length=255,
        db_column="estado"
    )

    fecha_inicio = models.DateTimeField(
        db_column="fecha_inicio",
        null=True,
        blank=True
    )

    fecha_fin = models.DateTimeField(
        db_column="fecha_fin",
        null=True,
        blank=True
    )

    fecha_registro = models.DateTimeField(
        db_column="fecha_registro"
    )

    fecha_actualizacion = models.DateTimeField(
        db_column="fecha_actualizacion"
    )


    class Meta:
        managed = False
        db_table = '"pedidos"."picking"'

        verbose_name = "Picking"
        verbose_name_plural = "Picking"


    def __str__(self):
        return f"Picking {self.id_picking}"



# =====================================================
# PICKING DETALLE
# =====================================================

class PickingDetalle(models.Model):

    id_picking_detalle = models.AutoField(
        primary_key=True,
        db_column="id_picking_detalle"
    )

    id_picking = models.IntegerField(
        db_column="id_picking"
    )

    id_reserva = models.IntegerField(
        db_column="id_reserva"
    )

    cantidad_solicitada = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        db_column="cantidad_solicitada"
    )

    cantidad_confirmada = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        db_column="cantidad_confirmada"
    )


    class Meta:
        managed = False
        db_table = '"pedidos"."picking_detalle"'

        verbose_name = "Detalle Picking"
        verbose_name_plural = "Detalles Picking"


    def __str__(self):
        return f"Picking detalle {self.id_picking_detalle}"

# =====================================================
# DESPACHO
# =====================================================

class Despacho(models.Model):

    id_despacho = models.AutoField(
        primary_key=True,
        db_column="id_despacho"
    )

    id_pedido_salida = models.IntegerField(
        db_column="id_pedido_salida"
    )

    codigo_documento_salida = models.CharField(
        max_length=255,
        db_column="codigo_documento_salida"
    )

    fecha_despacho = models.DateTimeField(
        db_column="fecha_despacho"
    )

    id_usuario_confirma = models.UUIDField(
        db_column="id_usuario_confirma"
    )

    observaciones = models.TextField(
        db_column="observaciones",
        null=True,
        blank=True
    )


    class Meta:
        managed = False
        db_table = '"pedidos"."despacho"'

        verbose_name = "Despacho"
        verbose_name_plural = "Despachos"


    def __str__(self):
        return self.codigo_documento_salida



# =====================================================
# DESPACHO DETALLE
# =====================================================

class DespachoDetalle(models.Model):

    id_despacho_detalle = models.AutoField(
        primary_key=True,
        db_column="id_despacho_detalle"
    )

    id_despacho = models.IntegerField(
        db_column="id_despacho"
    )

    id_picking_detalle = models.IntegerField(
        db_column="id_picking_detalle"
    )

    cantidad_despachada = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        db_column="cantidad_despachada"
    )


    class Meta:
        managed = False
        db_table = '"pedidos"."despacho_detalle"'

        verbose_name = "Detalle Despacho"
        verbose_name_plural = "Detalles Despacho"


    def __str__(self):
        return f"Despacho detalle {self.id_despacho_detalle}"



# =====================================================
# INCIDENCIA DESPACHO
# =====================================================

class IncidenciaDespacho(models.Model):

    id_incidencia_despacho = models.AutoField(
        primary_key=True,
        db_column="id_incidencia_despacho"
    )

    id_despacho = models.IntegerField(
        db_column="id_despacho"
    )

    id_despacho_detalle = models.IntegerField(
        db_column="id_despacho_detalle"
    )

    tipo = models.CharField(
        max_length=255,
        db_column="tipo"
    )

    cantidad = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        db_column="cantidad"
    )

    descripcion = models.TextField(
        db_column="descripcion",
        null=True,
        blank=True
    )

    fecha_registro = models.DateTimeField(
        db_column="fecha_registro"
    )

    fecha_actualizacion = models.DateTimeField(
        db_column="fecha_actualizacion"
    )


    class Meta:
        managed = False
        db_table = '"pedidos"."incidencia_despacho"'

        verbose_name = "Incidencia Despacho"
        verbose_name_plural = "Incidencias Despacho"


    def __str__(self):
        return self.tipo