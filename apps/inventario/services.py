from collections import defaultdict
from decimal import Decimal

from apps.maestros.models import Almacen, Cliente, Pallet, Producto, Ubicacion, Zona
from apps.usuarios.models import Usuario

from .models import Lote, MovimientoDetalle, Stock


STOCK_STATUS_LABELS = {
    "DISP": "Disponible",
    "BLOQ": "Bloqueado",
    "INV": "En inventario",
    "RES": "Reservado",
}


def _maps_for_stocks(stocks):
    product_ids = {item.id_producto for item in stocks}
    location_ids = {item.id_ubicacion for item in stocks}
    lot_ids = {item.id_lote for item in stocks if item.id_lote}
    pallet_ids = {item.id_pallet for item in stocks if item.id_pallet}

    products = {
        item.id_producto: item
        for item in Producto.objects.filter(id_producto__in=product_ids)
    }
    clients = {
        item.id_cliente: item
        for item in Cliente.objects.filter(
            id_cliente__in={item.id_cliente for item in products.values()}
        )
    }
    locations = {
        item.id_ubicacion: item
        for item in Ubicacion.objects.filter(id_ubicacion__in=location_ids)
    }
    zones = {
        item.id_zona: item
        for item in Zona.objects.filter(
            id_zona__in={item.id_zona for item in locations.values()}
        )
    }
    warehouses = {
        item.id_almacen: item
        for item in Almacen.objects.filter(
            id_almacen__in={item.id_almacen for item in zones.values()}
        )
    }
    lots = {
        item.id_lote: item
        for item in Lote.objects.filter(id_lote__in=lot_ids)
    }
    pallets = {
        item.id_pallet: item
        for item in Pallet.objects.filter(id_pallet__in=pallet_ids)
    }
    return products, clients, locations, zones, warehouses, lots, pallets


def serialize_stocks(queryset):
    stocks = list(queryset)
    (
        products,
        clients,
        locations,
        zones,
        warehouses,
        lots,
        pallets,
    ) = _maps_for_stocks(stocks)
    result = []
    for stock in stocks:
        product = products.get(stock.id_producto)
        client = clients.get(product.id_cliente) if product else None
        location = locations.get(stock.id_ubicacion)
        zone = zones.get(location.id_zona) if location else None
        warehouse = warehouses.get(zone.id_almacen) if zone else None
        lot = lots.get(stock.id_lote)
        pallet = pallets.get(stock.id_pallet)
        available = stock.cantidad_total - stock.cantidad_reservada
        result.append(
            {
                "id_stock": stock.id_stock,
                "producto": {
                    "id_producto": product.id_producto,
                    "sku": product.sku,
                    "nombre": product.nombre,
                }
                if product
                else None,
                "cliente": {
                    "id_cliente": client.id_cliente,
                    "razon_social": client.razon_social,
                }
                if client
                else None,
                "almacen": {
                    "id_almacen": warehouse.id_almacen,
                    "codigo": warehouse.codigo,
                    "nombre": warehouse.nombre,
                }
                if warehouse
                else None,
                "zona": {
                    "id_zona": zone.id_zona,
                    "codigo": zone.codigo,
                    "nombre": zone.nombre,
                }
                if zone
                else None,
                "ubicacion": {
                    "id_ubicacion": location.id_ubicacion,
                    "codigo": location.codigo,
                    "pasillo": location.pasillo,
                    "rack": location.rack,
                    "nivel": location.nivel,
                    "posicion": location.posicion,
                }
                if location
                else None,
                "lote": {
                    "id_lote": lot.id_lote,
                    "codigo": lot.codigo,
                    "fecha_vencimiento": lot.fecha_vencimiento,
                }
                if lot
                else None,
                "pallet": {
                    "id_pallet": pallet.id_pallet,
                    "codigo_barras": pallet.codigo_barras,
                    "id_pallet_padre": pallet.id_pallet_padre,
                }
                if pallet
                else None,
                "cantidad_total": stock.cantidad_total,
                "cantidad_reservada": stock.cantidad_reservada,
                "cantidad_disponible": available,
                "estado": stock.estado_stock,
                "estado_nombre": STOCK_STATUS_LABELS.get(
                    stock.estado_stock, stock.estado_stock
                ),
                "fecha_actualizacion": stock.fecha_actualizacion,
            }
        )
    return result


def serialize_movements(movements):
    movements = list(movements)
    movement_ids = [item.id_movimiento for item in movements]
    details = list(
        MovimientoDetalle.objects.filter(id_movimiento__in=movement_ids)
        .order_by("id_movimiento_detalle")
    )
    details_by_movement = defaultdict(list)
    for detail in details:
        details_by_movement[detail.id_movimiento].append(detail)

    stock_ids = {
        value
        for detail in details
        for value in (detail.id_stock_origen, detail.id_stock_destino)
        if value
    }
    stocks = {
        item.id_stock: item
        for item in Stock.objects.filter(id_stock__in=stock_ids)
    }
    stock_data = {
        item["id_stock"]: item
        for item in serialize_stocks(stocks.values())
    }
    location_ids = {
        value
        for detail in details
        for value in (
            detail.id_ubicacion_origen,
            detail.id_ubicacion_destino,
        )
    }
    locations = {
        item.id_ubicacion: item
        for item in Ubicacion.objects.filter(id_ubicacion__in=location_ids)
    }
    user_ids = {
        value
        for movement in movements
        for value in (
            movement.id_usuario_registro,
            movement.id_usuario_confirma,
        )
        if value
    }
    users = {
        str(item.id_usuario): item
        for item in Usuario.objects.filter(id_usuario__in=user_ids)
    }

    result = []
    for movement in movements:
        register_user = users.get(str(movement.id_usuario_registro))
        confirm_user = users.get(str(movement.id_usuario_confirma))
        serialized_details = []
        for detail in details_by_movement[movement.id_movimiento]:
            source = stock_data.get(detail.id_stock_origen)
            origin = locations.get(detail.id_ubicacion_origen)
            destination = locations.get(detail.id_ubicacion_destino)
            serialized_details.append(
                {
                    "id_movimiento_detalle": detail.id_movimiento_detalle,
                    "id_stock_origen": detail.id_stock_origen,
                    "id_stock_destino": detail.id_stock_destino,
                    "producto": source.get("producto") if source else None,
                    "cliente": source.get("cliente") if source else None,
                    "lote": source.get("lote") if source else None,
                    "pallet_origen": source.get("pallet") if source else None,
                    "id_pallet_destino": detail.id_pallet_destino,
                    "origen": {
                        "id_ubicacion": origin.id_ubicacion,
                        "codigo": origin.codigo,
                    }
                    if origin
                    else None,
                    "destino": {
                        "id_ubicacion": destination.id_ubicacion,
                        "codigo": destination.codigo,
                    }
                    if destination
                    else None,
                    "cantidad": detail.cantidad,
                }
            )
        result.append(
            {
                "id_movimiento": movement.id_movimiento,
                "tipo": movement.tipo_movimiento,
                "motivo": movement.motivo or "",
                "estado": movement.estado,
                "responsable_registro": _serialize_user(register_user),
                "responsable_confirmacion": _serialize_user(confirm_user),
                "fecha_registro": movement.fecha_registro,
                "fecha_confirmacion": movement.fecha_confirmacion,
                "lineas": serialized_details,
                "cantidad_total": sum(
                    (item.cantidad for item in details_by_movement[movement.id_movimiento]),
                    Decimal("0"),
                ),
            }
        )
    return result


def _serialize_user(user):
    if not user:
        return None
    return {
        "id_usuario": user.id_usuario,
        "nombre": user.nombre,
        "apellido": user.apellido,
        "correo": user.correo,
    }
