from collections import defaultdict
from decimal import Decimal

from apps.inventario.models import Lote, Reserva, Stock
from apps.maestros.models import Cliente, Producto, Ubicacion, UnidadMedida, Zona
from apps.usuarios.models import Usuario

from .models import (
    Despacho,
    DespachoDetalle,
    IncidenciaDespacho,
    PedidoDetalle,
    Picking,
    PickingDetalle,
)


def _user(user):
    if not user:
        return None
    return {
        "id_usuario": user.id_usuario,
        "nombre": user.nombre,
        "apellido": user.apellido,
        "correo": user.correo,
    }


def _duration_minutes(start, end):
    if not start or not end or end < start:
        return None
    return round((end - start).total_seconds() / 60, 2)


def serialize_orders(orders):
    orders = list(orders)
    order_ids = [item.id_pedido_salida for item in orders]
    details = list(
        PedidoDetalle.objects.filter(id_pedido_salida__in=order_ids)
        .order_by("id_pedido_detalle")
    )
    details_by_order = defaultdict(list)
    for detail in details:
        details_by_order[detail.id_pedido_salida].append(detail)

    product_ids = {item.id_producto for item in details}
    lot_ids = {item.id_lote for item in details if item.id_lote}
    unit_ids = {item.id_unidad_medida for item in details}
    products = {
        item.id_producto: item
        for item in Producto.objects.filter(id_producto__in=product_ids)
    }
    lots = {
        item.id_lote: item for item in Lote.objects.filter(id_lote__in=lot_ids)
    }
    units = {
        item.id_unidad_medida: item
        for item in UnidadMedida.objects.filter(id_unidad_medida__in=unit_ids)
    }
    clients = {
        item.id_cliente: item
        for item in Cliente.objects.filter(
            id_cliente__in={item.id_cliente for item in orders}
        )
    }

    pickings = {
        item.id_pedido_salida: item
        for item in Picking.objects.filter(id_pedido_salida__in=order_ids)
    }
    picking_details = list(
        PickingDetalle.objects.filter(
            id_picking__in=[item.id_picking for item in pickings.values()]
        ).order_by("id_picking_detalle")
    )
    picking_details_by_picking = defaultdict(list)
    for item in picking_details:
        picking_details_by_picking[item.id_picking].append(item)

    reservation_ids = {item.id_reserva for item in picking_details}
    reservations = {
        item.id_reserva: item
        for item in Reserva.objects.filter(id_reserva__in=reservation_ids)
    }
    stocks = {
        item.id_stock: item
        for item in Stock.objects.filter(
            id_stock__in={item.id_stock for item in reservations.values()}
        )
    }
    locations = {
        item.id_ubicacion: item
        for item in Ubicacion.objects.filter(
            id_ubicacion__in={item.id_ubicacion for item in stocks.values()}
        )
    }
    zones = {
        item.id_zona: item
        for item in Zona.objects.filter(
            id_zona__in={item.id_zona for item in locations.values()}
        )
    }

    dispatches = {
        item.id_pedido_salida: item
        for item in Despacho.objects.filter(id_pedido_salida__in=order_ids)
    }
    dispatch_details = list(DespachoDetalle.objects.filter(
        id_despacho__in=[item.id_despacho for item in dispatches.values()]
    ))
    dispatch_details_by_dispatch = defaultdict(list)
    for item in dispatch_details:
        dispatch_details_by_dispatch[item.id_despacho].append(item)
    dispatch_detail_by_id = {
        item.id_despacho_detalle: item for item in dispatch_details
    }
    picking_detail_by_id = {
        item.id_picking_detalle: item for item in picking_details
    }
    incidents = list(
        IncidenciaDespacho.objects.filter(
            id_despacho__in=[item.id_despacho for item in dispatches.values()]
        ).order_by("-fecha_registro")
    )
    incidents_by_dispatch = defaultdict(list)
    for item in incidents:
        incidents_by_dispatch[item.id_despacho].append(item)

    user_ids = {
        value
        for order in orders
        for value in (order.id_usuario_registro,)
        if value
    }
    user_ids.update(
        item.id_usuario_asignado for item in pickings.values()
    )
    user_ids.update(
        item.id_usuario_confirma for item in dispatches.values()
    )
    user_ids.update(
        item.id_usuario_registro for item in incidents if item.id_usuario_registro
    )
    users = {
        str(item.id_usuario): item
        for item in Usuario.objects.filter(id_usuario__in=user_ids)
    }

    current_stocks = list(
        Stock.objects.filter(id_producto__in=product_ids, estado_stock="DISP")
    )
    available_by_product_lot = defaultdict(Decimal)
    for stock in current_stocks:
        available_by_product_lot[(stock.id_producto, stock.id_lote)] += (
            stock.cantidad_total - stock.cantidad_reservada
        )

    result = []
    for order in orders:
        client = clients.get(order.id_cliente)
        picking = pickings.get(order.id_pedido_salida)
        order_picking_details = (
            picking_details_by_picking[picking.id_picking] if picking else []
        )
        preparation_by_order_detail = defaultdict(list)
        for item in order_picking_details:
            reservation = reservations.get(item.id_reserva)
            stock = stocks.get(reservation.id_stock) if reservation else None
            location = locations.get(stock.id_ubicacion) if stock else None
            zone = zones.get(location.id_zona) if location else None
            if reservation:
                preparation_by_order_detail[reservation.id_pedido_detalle].append(
                    {
                        "id_picking_detalle": item.id_picking_detalle,
                        "id_reserva": reservation.id_reserva,
                        "id_stock": reservation.id_stock,
                        "ubicacion": {
                            "id_ubicacion": location.id_ubicacion,
                            "codigo": location.codigo,
                            "zona": {
                                "id_zona": zone.id_zona,
                                "codigo": zone.codigo,
                                "nombre": zone.nombre,
                            }
                            if zone
                            else None,
                        }
                        if location
                        else None,
                        "cantidad_solicitada": item.cantidad_solicitada,
                        "cantidad_confirmada": item.cantidad_confirmada,
                        "estado_reserva": reservation.estado,
                    }
                )
        serialized_lines = []
        total_requested = Decimal("0")
        total_dispatched = Decimal("0")
        total_prepared = Decimal("0")
        for detail in details_by_order[order.id_pedido_salida]:
            product = products.get(detail.id_producto)
            lot = lots.get(detail.id_lote)
            unit = units.get(detail.id_unidad_medida)
            preparation = preparation_by_order_detail[detail.id_pedido_detalle]
            prepared = sum(
                (item["cantidad_confirmada"] for item in preparation), Decimal("0")
            )
            total_requested += detail.cantidad_solicitada
            total_dispatched += detail.cantidad_despachada
            total_prepared += prepared
            serialized_lines.append(
                {
                    "id_pedido_detalle": detail.id_pedido_detalle,
                    "producto": {
                        "id_producto": product.id_producto,
                        "sku": product.sku,
                        "nombre": product.nombre,
                        "controla_lote": product.controla_lote,
                    }
                    if product
                    else None,
                    "lote": {
                        "id_lote": lot.id_lote,
                        "codigo": lot.codigo,
                        "fecha_vencimiento": lot.fecha_vencimiento,
                    }
                    if lot
                    else None,
                    "unidad": {
                        "codigo": unit.codigo,
                        "nombre": unit.nombre,
                    }
                    if unit
                    else None,
                    "cantidad_solicitada": detail.cantidad_solicitada,
                    "cantidad_preparada": prepared,
                    "cantidad_despachada": detail.cantidad_despachada,
                    "stock_disponible": available_by_product_lot[
                        (detail.id_producto, detail.id_lote)
                    ],
                    "preparacion": preparation,
                }
            )
        dispatch = dispatches.get(order.id_pedido_salida)
        serialized_incidents = []
        order_incidents = (
            incidents_by_dispatch[dispatch.id_despacho] if dispatch else []
        )
        for incident in order_incidents:
            dispatch_detail = dispatch_detail_by_id.get(
                incident.id_despacho_detalle
            )
            picking_detail = (
                picking_detail_by_id.get(dispatch_detail.id_picking_detalle)
                if dispatch_detail
                else None
            )
            reservation = (
                reservations.get(picking_detail.id_reserva)
                if picking_detail
                else None
            )
            order_detail = next(
                (
                    item
                    for item in details_by_order[order.id_pedido_salida]
                    if reservation
                    and item.id_pedido_detalle == reservation.id_pedido_detalle
                ),
                None,
            )
            product = products.get(order_detail.id_producto) if order_detail else None
            serialized_incidents.append(
                {
                    "id_incidencia_despacho": incident.id_incidencia_despacho,
                    "tipo": incident.tipo,
                    "cantidad": incident.cantidad,
                    "descripcion": incident.descripcion or "",
                    "producto": {
                        "id_producto": product.id_producto,
                        "sku": product.sku,
                        "nombre": product.nombre,
                    }
                    if product
                    else None,
                    "responsable": _user(
                        users.get(str(incident.id_usuario_registro))
                    ),
                    "fecha_registro": incident.fecha_registro,
                }
            )
        preparation_minutes = _duration_minutes(
            picking.fecha_inicio if picking else None,
            picking.fecha_fin if picking else None,
        )
        dispatch_minutes = _duration_minutes(
            picking.fecha_fin if picking else None,
            dispatch.fecha_despacho if dispatch else None,
        )
        total_minutes = _duration_minutes(
            order.fecha_registro,
            dispatch.fecha_despacho if dispatch else None,
        )
        progress = (
            round(float(total_prepared / total_requested * 100), 2)
            if total_requested
            else 0
        )
        result.append(
            {
                "id_pedido_salida": order.id_pedido_salida,
                "codigo_documento": order.codigo_documento,
                "cliente": {
                    "id_cliente": client.id_cliente,
                    "razon_social": client.razon_social,
                    "ruc": client.ruc,
                }
                if client
                else None,
                "fecha_programada": order.fecha_programada,
                "fecha_despacho": order.fecha_despacho,
                "transporte_placa": order.transporte_placa or "",
                "transporte_conductor": order.transporte_conductor or "",
                "estado": order.estado,
                "responsable_registro": _user(
                    users.get(str(order.id_usuario_registro))
                ),
                "picking": {
                    "id_picking": picking.id_picking,
                    "estado": picking.estado,
                    "responsable": _user(
                        users.get(str(picking.id_usuario_asignado))
                    ),
                    "fecha_inicio": picking.fecha_inicio,
                    "fecha_fin": picking.fecha_fin,
                }
                if picking
                else None,
                "despacho": {
                    "id_despacho": dispatch.id_despacho,
                    "codigo_documento_salida": dispatch.codigo_documento_salida,
                    "fecha_despacho": dispatch.fecha_despacho,
                    "responsable": _user(
                        users.get(str(dispatch.id_usuario_confirma))
                    ),
                    "observaciones": dispatch.observaciones or "",
                    "cantidad_lineas": len(
                        dispatch_details_by_dispatch[dispatch.id_despacho]
                    ),
                    "incidencias": serialized_incidents,
                }
                if dispatch
                else None,
                "cantidad_solicitada": total_requested,
                "cantidad_preparada": total_prepared,
                "cantidad_despachada": total_dispatched,
                "progreso": min(progress, 100),
                "tiempos": {
                    "preparacion_minutos": preparation_minutes,
                    "despacho_minutos": dispatch_minutes,
                    "total_minutos": total_minutes,
                },
                "lineas": serialized_lines,
                "fecha_registro": order.fecha_registro,
                "fecha_actualizacion": order.fecha_actualizacion,
            }
        )
    return result
