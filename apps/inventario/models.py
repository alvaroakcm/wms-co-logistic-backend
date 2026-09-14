from django.db import models


# =====================================================
# LOTE
# =====================================================

class Lote(models.Model):

    id_lote = models.AutoField(
        primary_key=True,
        db_column="id_lote"
    )

    id_producto = models.IntegerField(
        db_column="id_producto"
    )

    codigo = models.CharField(
        max_length=255,
        db_column="codigo"
    )

    fecha_fabricacion = models.DateField(
        db_column="fecha_fabricacion",
        null=True,
        blank=True
    )

    fecha_vencimiento = models.DateField(
        db_column="fecha_vencimiento",
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
        db_table = '"inventario"."lote"'

        verbose_name = "Lote"
        verbose_name_plural = "Lotes"


    def __str__(self):
        return self.codigo



# =====================================================
# STOCK
# =====================================================

class Stock(models.Model):

    id_stock = models.AutoField(
        primary_key=True,
        db_column="id_stock"
    )

    id_producto = models.IntegerField(
        db_column="id_producto"
    )

    id_lote = models.IntegerField(
        db_column="id_lote",
        null=True,
        blank=True
    )

    id_ubicacion = models.IntegerField(
        db_column="id_ubicacion"
    )

    id_pallet = models.IntegerField(
        db_column="id_pallet",
        null=True,
        blank=True
    )

    cantidad_total = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        db_column="cantidad_total"
    )

    cantidad_reservada = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        db_column="cantidad_reservada"
    )

    estado_stock = models.CharField(
        max_length=20,
        db_column="estado_stock"
    )

    fecha_actualizacion = models.DateTimeField(
        db_column="fecha_actualizacion"
    )


    class Meta:
        managed = False
        db_table = '"inventario"."stock"'

        verbose_name = "Stock"
        verbose_name_plural = "Stocks"


    def __str__(self):
        return f"Stock {self.id_stock}"

# =====================================================
# MOVIMIENTO
# =====================================================

class Movimiento(models.Model):

    id_movimiento = models.AutoField(
        primary_key=True,
        db_column="id_movimiento"
    )

    tipo_movimiento = models.CharField(
        max_length=255,
        db_column="tipo_movimiento"
    )

    motivo = models.CharField(
        max_length=255,
        db_column="motivo"
    )

    id_usuario_registro = models.UUIDField(
        db_column="id_usuario_registro"
    )

    id_usuario_confirma = models.UUIDField(
        db_column="id_usuario_confirma",
        null=True,
        blank=True
    )

    fecha_registro = models.DateTimeField(
        db_column="fecha_registro"
    )

    fecha_actualizacion = models.DateTimeField(
        db_column="fecha_actualizacion"
    )

    fecha_confirmacion = models.DateTimeField(
        db_column="fecha_confirmacion",
        null=True,
        blank=True
    )


    class Meta:
        managed = False
        db_table = '"inventario"."movimiento"'

        verbose_name = "Movimiento"
        verbose_name_plural = "Movimientos"


    def __str__(self):
        return self.tipo_movimiento



# =====================================================
# MOVIMIENTO DETALLE
# =====================================================

class MovimientoDetalle(models.Model):

    id_movimiento_detalle = models.AutoField(
        primary_key=True,
        db_column="id_movimiento_detalle"
    )

    id_movimiento = models.IntegerField(
        db_column="id_movimiento"
    )

    id_stock_origen = models.IntegerField(
        db_column="id_stock_origen"
    )

    id_ubicacion_destino = models.IntegerField(
        db_column="id_ubicacion_destino"
    )

    id_pallet_destino = models.IntegerField(
        db_column="id_pallet_destino"
    )

    cantidad = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        db_column="cantidad"
    )


    class Meta:
        managed = False
        db_table = '"inventario"."movimiento_detalle"'

        verbose_name = "Movimiento Detalle"
        verbose_name_plural = "Detalles Movimiento"


    def __str__(self):
        return f"Movimiento {self.id_movimiento}"

# =====================================================
# RESERVA
# =====================================================

class Reserva(models.Model):

    id_reserva = models.AutoField(
        primary_key=True,
        db_column="id_reserva"
    )

    id_stock = models.IntegerField(
        db_column="id_stock"
    )

    id_pedido_detalle = models.IntegerField(
        db_column="id_pedido_detalle"
    )

    cantidad = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        db_column="cantidad"
    )

    estado = models.CharField(
        max_length=255,
        db_column="estado"
    )

    fecha_registro = models.DateTimeField(
        db_column="fecha_registro"
    )

    fecha_actualizacion = models.DateTimeField(
        db_column="fecha_actualizacion"
    )


    class Meta:
        managed = False
        db_table = '"inventario"."reserva"'

        verbose_name = "Reserva"
        verbose_name_plural = "Reservas"


    def __str__(self):
        return f"Reserva {self.id_reserva}"



# =====================================================
# ASIGNACION UBICACION
# =====================================================

class AsignacionUbicacion(models.Model):

    id_asignacion_ubicacion = models.AutoField(
        primary_key=True,
        db_column="id_asignacion_ubicacion"
    )

    id_stock = models.IntegerField(
        db_column="id_stock"
    )

    id_pedido_ingreso = models.IntegerField(
        db_column="id_pedido_ingreso"
    )

    id_ubicacion = models.IntegerField(
        db_column="id_ubicacion"
    )

    id_pallet = models.IntegerField(
        db_column="id_pallet"
    )

    cantidad = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        db_column="cantidad"
    )

    id_usuario_responsable = models.UUIDField(
        db_column="id_usuario_responsable"
    )

    fecha_asignacion = models.DateTimeField(
        db_column="fecha_asignacion"
    )


    class Meta:
        managed = False
        db_table = '"inventario"."asignacion_ubicacion"'

        verbose_name = "Asignación Ubicación"
        verbose_name_plural = "Asignaciones Ubicación"


    def __str__(self):
        return f"Asignación {self.id_asignacion_ubicacion}"



# =====================================================
# VISTA STOCK DISPONIBLE
# =====================================================

class VStockDisponible(models.Model):

    id_stock = models.IntegerField(
        primary_key=True,
        db_column="id_stock"
    )

    cliente_nombre = models.CharField(
        max_length=255,
        db_column="cliente_nombre"
    )

    producto_ean = models.CharField(
        max_length=255,
        db_column="producto_ean"
    )

    producto_nombre = models.CharField(
        max_length=255,
        db_column="producto_nombre"
    )

    lote_codigo = models.CharField(
        max_length=255,
        db_column="lote_codigo"
    )

    fecha_vencimiento = models.DateField(
        db_column="fecha_vencimiento"
    )

    ubicacion_codigo = models.CharField(
        max_length=255,
        db_column="ubicacion_codigo"
    )

    cantidad_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        db_column="cantidad_total"
    )

    cantidad_reservada = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        db_column="cantidad_reservada"
    )

    cantidad_disponible = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        db_column="cantidad_disponible"
    )

    estado_stock = models.CharField(
        max_length=255,
        db_column="estado_stock"
    )


    class Meta:
        managed = False
        db_table = '"inventario"."v_stock_disponible"'

        verbose_name = "Stock Disponible"
        verbose_name_plural = "Stock Disponible"



    def __str__(self):
        return self.producto_nombre
