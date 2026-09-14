from django.contrib import admin

from .models import (
    Almacen,
    CategoriaProducto,
    Cliente,
    Producto,
    Ubicacion,
    UnidadMedida,
    Zona,
)


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("ruc", "razon_social", "contacto_nombre", "estado")
    list_filter = ("estado",)
    search_fields = ("ruc", "razon_social", "contacto_nombre")


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ("sku", "codigo_ean", "nombre", "id_cliente", "estado")
    list_filter = ("estado", "controla_lote")
    search_fields = ("sku", "codigo_ean", "nombre")


admin.site.register(CategoriaProducto)
admin.site.register(UnidadMedida)
admin.site.register(Almacen)
admin.site.register(Zona)
admin.site.register(Ubicacion)
