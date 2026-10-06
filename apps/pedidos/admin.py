from django.contrib import admin

from .models import (
    Despacho,
    DespachoDetalle,
    IncidenciaDespacho,
    PedidoDetalle,
    PedidoSalida,
    Picking,
    PickingDetalle,
)


@admin.register(PedidoSalida)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("codigo_documento", "id_cliente", "fecha_programada", "estado")
    list_filter = ("estado",)
    search_fields = ("codigo_documento",)


@admin.register(PedidoDetalle)
class OrderDetailAdmin(admin.ModelAdmin):
    list_display = ("id_pedido_detalle", "id_pedido_salida", "id_producto", "id_lote", "cantidad_solicitada", "cantidad_despachada")


@admin.register(Picking)
class PickingAdmin(admin.ModelAdmin):
    list_display = ("id_picking", "id_pedido_salida", "estado", "id_usuario_asignado")
    list_filter = ("estado",)


admin.site.register(PickingDetalle)
admin.site.register(Despacho)
admin.site.register(DespachoDetalle)
admin.site.register(IncidenciaDespacho)
