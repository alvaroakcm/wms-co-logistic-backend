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

    tipo_servicio = models.CharField(
        max_length=255,
        db_column="tipo_servicio"
    )

    estado = models.CharField(
        max_length=255,
        db_column="estado"
    )

    tarifa_aplicada = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        db_column="tarifa_aplicada"
    )

    id_usuario_registro = models.UUIDField(
        db_column="id_usuario_registro"
    )

    fecha_servicio = models.DateTimeField(
        db_column="fecha_servicio"
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
        db_column="id_pallet_origen"
    )

    id_pallet_destino = models.IntegerField(
        db_column="id_pallet_destino"
    )

    cantidad_pallets = models.IntegerField(
        db_column="cantidad_pallets"
    )


    class Meta:
        managed = False
        db_table = '"servicios"."repaletizado"'

        verbose_name = "Repaletizado"
        verbose_name_plural = "Repaletizados"


    def __str__(self):
        return f"Repaletizado {self.id_repaletizado}"