from django.contrib import admin

from .models import (
    ASN,
    Discrepancia,
    IncidenciaRecepcion,
    PedidoIngreso,
    PedidoIngresoDetalle,
    PedidoIngresoLote,
)


@admin.register(PedidoIngreso)
class PedidoIngresoAdmin(admin.ModelAdmin):
    list_display = (
        "codigo_documento",
        "id_cliente",
        "estado",
        "fecha_programada",
        "fecha_recepcion",
    )
    list_filter = ("estado", "fecha_programada")
    search_fields = ("codigo_documento", "transporte_placa")


@admin.register(PedidoIngresoDetalle)
class PedidoIngresoDetalleAdmin(admin.ModelAdmin):
    list_display = (
        "id_pedido_ingreso",
        "codigo_producto",
        "cantidad_esperada",
        "cantidad_recibida",
        "cantidad_rechazada",
    )
    search_fields = ("codigo_producto", "descripcion_producto")


@admin.register(Discrepancia)
class DiscrepanciaAdmin(admin.ModelAdmin):
    list_display = ("id_pedido_ingreso", "tipo", "cantidad", "fecha_registro")
    list_filter = ("tipo",)


@admin.register(IncidenciaRecepcion)
class IncidenciaRecepcionAdmin(admin.ModelAdmin):
    list_display = (
        "id_pedido_ingreso",
        "tipo",
        "cantidad_afectada",
        "id_usuario_responsable",
        "fecha_registro",
    )
    list_filter = ("tipo",)
    search_fields = ("descripcion",)


@admin.register(PedidoIngresoLote)
class PedidoIngresoLoteAdmin(admin.ModelAdmin):
    list_display = (
        "id_pedido_ingreso_detalle",
        "id_lote",
        "cantidad",
        "fecha_registro",
    )


admin.site.register(ASN)
