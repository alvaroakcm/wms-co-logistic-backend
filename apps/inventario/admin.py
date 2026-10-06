from django.contrib import admin

from .models import Lote, Movimiento, MovimientoDetalle, Stock


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = (
        "id_stock",
        "id_producto",
        "id_ubicacion",
        "cantidad_total",
        "cantidad_reservada",
        "estado_stock",
    )
    list_filter = ("estado_stock",)
    search_fields = ("id_stock", "id_producto", "id_ubicacion")


@admin.register(Lote)
class LoteAdmin(admin.ModelAdmin):
    list_display = ("codigo", "id_producto", "fecha_vencimiento")
    search_fields = ("codigo",)


@admin.register(Movimiento)
class MovementAdmin(admin.ModelAdmin):
    list_display = (
        "id_movimiento",
        "tipo_movimiento",
        "estado",
        "fecha_registro",
        "fecha_confirmacion",
    )
    list_filter = ("tipo_movimiento", "estado")


@admin.register(MovimientoDetalle)
class MovementDetailAdmin(admin.ModelAdmin):
    list_display = (
        "id_movimiento_detalle",
        "id_movimiento",
        "id_stock_origen",
        "id_ubicacion_origen",
        "id_ubicacion_destino",
        "cantidad",
    )
