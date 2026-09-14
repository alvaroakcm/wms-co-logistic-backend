from decimal import Decimal

from django.db.models import Sum

from apps.inventario.models import Stock

from .models import (
    Almacen,
    CategoriaProducto,
    Cliente,
    ProductoConversion,
    UnidadMedida,
    Zona,
)


def serialize_client(client):
    return {
        "id_cliente": client.id_cliente,
        "razon_social": client.razon_social,
        "ruc": client.ruc,
        "contacto_nombre": client.contacto_nombre or "",
        "contacto_telefono": client.contacto_telefono or "",
        "estado": client.estado,
        "fecha_registro": client.fecha_registro,
        "fecha_actualizacion": client.fecha_actualizacion,
    }


def serialize_products(products):
    products = list(products)
    product_ids = {product.id_producto for product in products}
    pallet_unit = UnidadMedida.objects.filter(codigo__iexact="PLT").first()
    conversions = {}
    if pallet_unit and product_ids:
        conversions = {
            conversion.id_producto: conversion
            for conversion in ProductoConversion.objects.filter(
                id_producto__in=product_ids,
                id_unidad_origen=pallet_unit.id_unidad_medida,
            ).order_by("id_producto_conversion")
        }
    clients = {
        item.id_cliente: item
        for item in Cliente.objects.filter(
            id_cliente__in={product.id_cliente for product in products}
        )
    }
    categories = {
        item.id_categoria: item
        for item in CategoriaProducto.objects.filter(
            id_categoria__in={
                product.id_categoria
                for product in products
                if product.id_categoria is not None
            }
        )
    }
    units = {
        item.id_unidad_medida: item
        for item in UnidadMedida.objects.filter(
            id_unidad_medida__in={
                product.id_unidad_medida for product in products
            }
        )
    }

    result = []
    for product in products:
        client = clients.get(product.id_cliente)
        category = categories.get(product.id_categoria)
        unit = units.get(product.id_unidad_medida)
        conversion = conversions.get(product.id_producto)
        result.append(
            {
                "id_producto": product.id_producto,
                "id_cliente": product.id_cliente,
                "cliente": (
                    {
                        "id_cliente": client.id_cliente,
                        "razon_social": client.razon_social,
                        "ruc": client.ruc,
                    }
                    if client
                    else None
                ),
                "id_categoria": product.id_categoria,
                "categoria": category.nombre if category else None,
                "id_unidad_medida": product.id_unidad_medida,
                "unidad_medida": (
                    {"codigo": unit.codigo, "nombre": unit.nombre}
                    if unit
                    else None
                ),
                "unidad_comercial": (
                    "CAJA" if unit and unit.codigo.strip().upper() == "CJ" else "UNIDAD"
                ),
                "factor_conversion": (
                    str(conversion.factor_conversion) if conversion else None
                ),
                "sku": product.sku,
                "codigo_ean": product.codigo_ean,
                "nombre": product.nombre,
                "descripcion": product.descripcion or "",
                "controla_lote": product.controla_lote,
                "estado": product.estado,
                "fecha_registro": product.fecha_registro,
                "fecha_actualizacion": product.fecha_actualizacion,
            }
        )
    return result


def sync_product_conversion(product, factor_conversion):
    """Mantiene la conversión comercial PLT -> CJ de un producto."""
    pallet_unit = UnidadMedida.objects.filter(
        codigo__iexact="PLT", estado=True
    ).first()
    if pallet_unit is None:
        if factor_conversion is None:
            return
        raise UnidadMedida.DoesNotExist("La unidad Pallet (PLT) no está activa.")
    query = ProductoConversion.objects.filter(
        id_producto=product.id_producto,
        id_unidad_origen=pallet_unit.id_unidad_medida,
    )
    query.delete()
    if factor_conversion is not None:
        ProductoConversion.objects.create(
            id_producto=product.id_producto,
            id_unidad_origen=pallet_unit.id_unidad_medida,
            id_unidad_destino=product.id_unidad_medida,
            factor_conversion=factor_conversion,
        )


def calculate_product_boxes(product, pallet_quantity):
    pallet_unit = UnidadMedida.objects.filter(
        codigo__iexact="PLT", estado=True
    ).first()
    if pallet_unit is None:
        return None
    conversion = ProductoConversion.objects.filter(
        id_producto=product.id_producto,
        id_unidad_origen=pallet_unit.id_unidad_medida,
        id_unidad_destino=product.id_unidad_medida,
    ).first()
    if conversion is None:
        return None
    return pallet_quantity * conversion.factor_conversion


def serialize_warehouse(warehouse):
    return {
        "id_almacen": warehouse.id_almacen,
        "codigo": warehouse.codigo,
        "nombre": warehouse.nombre,
        "referencia": warehouse.referencia or "",
        "capacidad_pallets": warehouse.capacidad_pallets,
        "estado": warehouse.estado,
        "fecha_registro": warehouse.fecha_registro,
        "fecha_actualizacion": warehouse.fecha_actualizacion,
    }


def serialize_zone(zone, warehouses=None):
    warehouse = (warehouses or {}).get(zone.id_almacen)
    return {
        "id_zona": zone.id_zona,
        "id_almacen": zone.id_almacen,
        "almacen": (
            {
                "id_almacen": warehouse.id_almacen,
                "codigo": warehouse.codigo,
                "nombre": warehouse.nombre,
            }
            if warehouse
            else None
        ),
        "codigo": zone.codigo,
        "nombre": zone.nombre,
        "tipo": zone.tipo,
        "estado": zone.estado,
        "fecha_registro": zone.fecha_registro,
        "fecha_actualizacion": zone.fecha_actualizacion,
    }


def serialize_locations(locations):
    locations = list(locations)
    zones = {
        zone.id_zona: zone
        for zone in Zona.objects.filter(
            id_zona__in={location.id_zona for location in locations}
        )
    }
    warehouses = {
        warehouse.id_almacen: warehouse
        for warehouse in Almacen.objects.filter(
            id_almacen__in={zone.id_almacen for zone in zones.values()}
        )
    }
    stock_totals = {
        row["id_ubicacion"]: row["total"] or Decimal("0")
        for row in Stock.objects.filter(
            id_ubicacion__in={location.id_ubicacion for location in locations},
            cantidad_total__gt=0,
        )
        .values("id_ubicacion")
        .annotate(total=Sum("cantidad_total"))
    }

    result = []
    for location in locations:
        zone = zones.get(location.id_zona)
        warehouse = warehouses.get(zone.id_almacen) if zone else None
        stock_total = stock_totals.get(location.id_ubicacion, Decimal("0"))
        operational_status = (
            "inactiva"
            if not location.estado
            else "ocupada"
            if stock_total > 0
            else "disponible"
        )
        result.append(
            {
                "id_ubicacion": location.id_ubicacion,
                "id_zona": location.id_zona,
                "zona": (
                    {
                        "id_zona": zone.id_zona,
                        "codigo": zone.codigo,
                        "nombre": zone.nombre,
                    }
                    if zone
                    else None
                ),
                "almacen": (
                    {
                        "id_almacen": warehouse.id_almacen,
                        "codigo": warehouse.codigo,
                        "nombre": warehouse.nombre,
                    }
                    if warehouse
                    else None
                ),
                "codigo": location.codigo,
                "pasillo": location.pasillo,
                "rack": location.rack,
                "nivel": location.nivel,
                "columna": location.columna,
                "posicion": location.posicion,
                "capacidad_volumen": location.capacidad_volumen,
                "capacidad_peso": location.capacidad_peso,
                "stock_total": stock_total,
                "estado_operativo": operational_status,
                "estado": location.estado,
                "fecha_registro": location.fecha_registro,
                "fecha_actualizacion": location.fecha_actualizacion,
            }
        )
    return result
