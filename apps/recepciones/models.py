from django.db import models


# =====================================================
# PEDIDO INGRESO
# =====================================================

class PedidoIngreso(models.Model):

    id_pedido_ingreso = models.AutoField(
        primary_key=True,
        db_column="id_pedido_ingreso"
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

    fecha_recepcion = models.DateTimeField(
        db_column="fecha_recepcion",
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
        db_table = '"recepcion"."pedido_ingreso"'

        verbose_name = "Pedido Ingreso"
        verbose_name_plural = "Pedidos Ingreso"


    def __str__(self):
        return self.codigo_documento



# =====================================================
# PEDIDO INGRESO DETALLE
# =====================================================

class PedidoIngresoDetalle(models.Model):

    id_pedido_ingreso_detalle = models.AutoField(
        primary_key=True,
        db_column="id_pedido_ingreso_detalle"
    )

    id_pedido_ingreso = models.IntegerField(
        db_column="id_pedido_ingreso"
    )

    id_producto = models.IntegerField(
        db_column="id_producto"
    )

    cantidad_esperada = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        db_column="cantidad_esperada"
    )

    cantidad_recibida = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        db_column="cantidad_recibida"
    )

    cantidad_rechazada = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        db_column="cantidad_rechazada"
    )

    id_unidad_medida = models.IntegerField(
        db_column="id_unidad_medida"
    )


    class Meta:
        managed = False
        db_table = '"recepcion"."pedido_ingreso_detalle"'

        verbose_name = "Detalle Pedido Ingreso"
        verbose_name_plural = "Detalles Pedido Ingreso"


    def __str__(self):
        return f"Detalle {self.id_pedido_ingreso_detalle}"

# =====================================================
# ASN
# =====================================================

class ASN(models.Model):

    id_asn = models.AutoField(
        primary_key=True,
        db_column="id_asn"
    )

    id_pedido_ingreso = models.IntegerField(
        db_column="id_pedido_ingreso"
    )

    codigo_asn = models.CharField(
        max_length=255,
        db_column="codigo_asn"
    )

    fecha_envio = models.DateTimeField(
        db_column="fecha_envio"
    )

    fecha_estimada = models.DateTimeField(
        db_column="fecha_estimada"
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
        db_table = '"recepcion"."asn"'

        verbose_name = "ASN"
        verbose_name_plural = "ASN"


    def __str__(self):
        return self.codigo_asn



# =====================================================
# DISCREPANCIA
# =====================================================

class Discrepancia(models.Model):

    id_discrepancia = models.AutoField(
        primary_key=True,
        db_column="id_discrepancia"
    )

    id_pedido_ingreso = models.IntegerField(
        db_column="id_pedido_ingreso"
    )

    id_pedido_ingreso_detalle = models.IntegerField(
        db_column="id_pedido_ingreso_detalle"
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
        db_table = '"recepcion"."discrepancia"'

        verbose_name = "Discrepancia"
        verbose_name_plural = "Discrepancias"


    def __str__(self):
        return self.tipo