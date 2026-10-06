from collections import Counter, defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from apps.inventario.models import Lote, Movimiento, MovimientoDetalle, Reserva, Stock
from apps.inventario.services import serialize_movements, serialize_stocks
from apps.maestros.models import Almacen, Cliente, Producto, Ubicacion, Zona
from apps.pedidos.models import (
    Despacho,
    DespachoDetalle,
    IncidenciaDespacho,
    PedidoDetalle,
    PedidoSalida,
    Picking,
    PickingDetalle,
)
from apps.pedidos.services import serialize_orders
from apps.recepciones.models import (
    Discrepancia,
    IncidenciaRecepcion,
    PedidoIngreso,
    PedidoIngresoDetalle,
    PedidoIngresoLote,
)
from apps.recepciones.services import serialize_receipts
from apps.usuarios.models import Usuario


def decimal_text(value):
    return str(value if value is not None else Decimal("0"))


def period_bounds(date_from=None, date_to=None):
    today = timezone.localdate()
    return date_from or today - timedelta(days=29), date_to or today


def occupancy_report(warehouse_term=""):
    warehouses = list(Almacen.objects.filter(estado=True).order_by("nombre"))
    if warehouse_term:
        warehouses = [
            item for item in warehouses
            if warehouse_term.lower() in item.nombre.lower()
            or warehouse_term.lower() in item.codigo.lower()
            or str(item.id_almacen) == warehouse_term
        ]
    warehouse_ids = [item.id_almacen for item in warehouses]
    zones = list(Zona.objects.filter(id_almacen__in=warehouse_ids, estado=True).order_by("nombre"))
    zone_map = {item.id_zona: item for item in zones}
    locations = list(Ubicacion.objects.filter(id_zona__in=list(zone_map), estado=True).order_by("codigo"))
    stocks = list(Stock.objects.filter(id_ubicacion__in=[item.id_ubicacion for item in locations], cantidad_total__gt=0))
    stocks_by_location = defaultdict(list)
    for stock in stocks:
        stocks_by_location[stock.id_ubicacion].append(stock)

    rows = []
    for warehouse in warehouses:
        warehouse_zones = [item for item in zones if item.id_almacen == warehouse.id_almacen]
        warehouse_locations = [item for item in locations if zone_map[item.id_zona].id_almacen == warehouse.id_almacen]
        occupied_pallets = {stock.id_pallet for stock in stocks if stock.id_pallet and stock.id_ubicacion in {item.id_ubicacion for item in warehouse_locations}}
        unpalletized = {
            location.id_ubicacion for location in warehouse_locations
            if stocks_by_location[location.id_ubicacion]
            and not any(item.id_pallet for item in stocks_by_location[location.id_ubicacion])
        }
        used = len(occupied_pallets) + len(unpalletized)
        capacity = max(warehouse.capacidad_pallets, 0)
        zone_rows = []
        for zone in warehouse_zones:
            zone_locations = [item for item in warehouse_locations if item.id_zona == zone.id_zona]
            occupied = sum(bool(stocks_by_location[item.id_ubicacion]) for item in zone_locations)
            zone_capacity = len(zone_locations)
            zone_rows.append({
                "id_zona": zone.id_zona,
                "codigo": zone.codigo,
                "nombre": zone.nombre,
                "tipo": zone.tipo,
                "capacidad": zone_capacity,
                "utilizada": occupied,
                "disponible": max(zone_capacity - occupied, 0),
                "porcentaje": round((occupied / zone_capacity) * 100, 2) if zone_capacity else 0,
            })
        rows.append({
            "id_almacen": warehouse.id_almacen,
            "codigo": warehouse.codigo,
            "nombre": warehouse.nombre,
            "capacidad": capacity,
            "utilizada": used,
            "disponible": max(capacity - used, 0),
            "porcentaje": round((used / capacity) * 100, 2) if capacity else 0,
            "ubicaciones_ocupadas": sum(bool(stocks_by_location[item.id_ubicacion]) for item in warehouse_locations),
            "ubicaciones_libres": sum(not stocks_by_location[item.id_ubicacion] for item in warehouse_locations),
            "zonas": zone_rows,
        })
    return rows


def _average_minutes(pairs):
    values = [(end - start).total_seconds() / 60 for start, end in pairs if start and end and end >= start]
    return round(sum(values) / len(values), 2) if values else 0


def dashboard_report(date_from=None, date_to=None, warehouse=""):
    date_from, date_to = period_bounds(date_from, date_to)
    stocks = list(Stock.objects.all())
    stock_product_ids = {item.id_producto for item in stocks}
    stock_location_ids = {item.id_ubicacion for item in stocks if item.cantidad_total > 0}
    total_stock = sum((item.cantidad_total for item in stocks), Decimal("0"))
    reserved_stock = sum((item.cantidad_reservada for item in stocks), Decimal("0"))

    receipts = list(PedidoIngreso.objects.filter(fecha_registro__date__range=(date_from, date_to)))
    receipt_ids = [item.id_pedido_ingreso for item in receipts]
    receipt_details = list(PedidoIngresoDetalle.objects.filter(id_pedido_ingreso__in=receipt_ids))
    orders = list(PedidoSalida.objects.filter(fecha_registro__date__range=(date_from, date_to)))
    order_ids = [item.id_pedido_salida for item in orders]
    order_details = list(PedidoDetalle.objects.filter(id_pedido_salida__in=order_ids))
    movements = list(Movimiento.objects.filter(fecha_registro__date__range=(date_from, date_to)))
    dispatches = list(Despacho.objects.filter(id_pedido_salida__in=order_ids))
    receipt_incidents = list(IncidenciaRecepcion.objects.filter(id_pedido_ingreso__in=receipt_ids))
    dispatch_incidents = list(IncidenciaDespacho.objects.filter(id_despacho__in=[item.id_despacho for item in dispatches]))
    pickings = list(Picking.objects.filter(id_pedido_salida__in=order_ids))

    daily = {date_from + timedelta(days=index): {"recepciones": 0, "despachos": 0, "movimientos": 0} for index in range((date_to - date_from).days + 1)}
    for item in receipts:
        daily[item.fecha_registro.date()]["recepciones"] += 1
    for item in orders:
        if item.fecha_despacho and item.fecha_despacho.date() in daily:
            daily[item.fecha_despacho.date()]["despachos"] += 1
    for item in movements:
        daily[item.fecha_registro.date()]["movimientos"] += 1

    users = {str(item.id_usuario): item for item in Usuario.objects.all()}
    operations = Counter()
    for item in receipts:
        operations[str(item.id_usuario_registro)] += 1
    for item in movements:
        operations[str(item.id_usuario_registro)] += 1
        if item.id_usuario_confirma:
            operations[str(item.id_usuario_confirma)] += 1
    for item in orders:
        operations[str(item.id_usuario_registro)] += 1
    for item in dispatches:
        operations[str(item.id_usuario_confirma)] += 1

    occupancy = occupancy_report(warehouse)
    used_capacity = sum(item["utilizada"] for item in occupancy)
    total_capacity = sum(item["capacidad"] for item in occupancy)
    return {
        "periodo": {"desde": date_from, "hasta": date_to},
        "kpis": {
            "inventario_total": total_stock,
            "inventario_disponible": total_stock - reserved_stock,
            "inventario_reservado": reserved_stock,
            "productos_con_stock": len(stock_product_ids),
            "ubicaciones_ocupadas": len(stock_location_ids),
            "ocupacion_porcentaje": round((used_capacity / total_capacity) * 100, 2) if total_capacity else 0,
            "recepciones": len(receipts),
            "unidades_recibidas": sum((item.cantidad_recibida for item in receipt_details), Decimal("0")),
            "despachos": len(dispatches),
            "unidades_despachadas": sum((item.cantidad_despachada for item in order_details), Decimal("0")),
            "movimientos_internos": len(movements),
            "incidencias": len(receipt_incidents) + len(dispatch_incidents),
        },
        "ocupacion": occupancy,
        "alertas_ocupacion": [item for item in occupancy if item["porcentaje"] >= 85],
        "tendencia": [{"fecha": date, **values} for date, values in daily.items()],
        "desempeno": {
            "tiempo_recepcion_minutos": _average_minutes((item.fecha_registro, item.fecha_recepcion) for item in receipts),
            "tiempo_preparacion_minutos": _average_minutes((item.fecha_inicio, item.fecha_fin) for item in pickings),
            "tiempo_despacho_minutos": _average_minutes((item.fecha_registro, item.fecha_despacho) for item in orders),
            "operaciones_por_responsable": [
                {
                    "id_usuario": user_id,
                    "responsable": (
                        f"{users[user_id].nombre} {users[user_id].apellido}".strip()
                        if user_id in users else "Usuario no disponible"
                    ),
                    "operaciones": total,
                }
                for user_id, total in operations.most_common()
            ],
        },
        "recepciones_recientes": serialize_receipts(sorted(receipts, key=lambda item: item.fecha_registro, reverse=True)[:5]),
        "despachos_en_proceso": serialize_orders([item for item in sorted(orders, key=lambda item: item.fecha_registro, reverse=True) if item.estado not in {"CERRADO", "CANCELADO"}][:5]),
    }


def movement_report(filters):
    query = Movimiento.objects.all().order_by("-fecha_registro", "-id_movimiento")
    if filters.get("fecha_desde"):
        query = query.filter(fecha_registro__date__gte=filters["fecha_desde"])
    if filters.get("fecha_hasta"):
        query = query.filter(fecha_registro__date__lte=filters["fecha_hasta"])
    if filters.get("tipo"):
        query = query.filter(tipo_movimiento=filters["tipo"].upper())
    if filters.get("estado"):
        query = query.filter(estado=filters["estado"].upper())
    responsible = filters.get("responsable", "")
    if responsible:
        user_ids = Usuario.objects.filter(Q(nombre__icontains=responsible) | Q(apellido__icontains=responsible) | Q(correo__icontains=responsible)).values_list("id_usuario", flat=True)
        query = query.filter(Q(id_usuario_registro__in=user_ids) | Q(id_usuario_confirma__in=user_ids))

    details = MovimientoDetalle.objects.all()
    product_ids = Producto.objects.all().values_list("id_producto", flat=True)
    product = filters.get("producto", "")
    client = filters.get("cliente", "")
    if product:
        product_ids = Producto.objects.filter(Q(sku__icontains=product) | Q(nombre__icontains=product)).values_list("id_producto", flat=True)
    if client:
        client_ids = Cliente.objects.filter(Q(razon_social__icontains=client) | Q(ruc__icontains=client)).values_list("id_cliente", flat=True)
        product_ids = Producto.objects.filter(id_producto__in=product_ids, id_cliente__in=client_ids).values_list("id_producto", flat=True)
    if product or client:
        stock_ids = Stock.objects.filter(id_producto__in=product_ids).values_list("id_stock", flat=True)
        details = details.filter(id_stock_origen__in=stock_ids)
    location = filters.get("ubicacion", "")
    if location:
        location_ids = Ubicacion.objects.filter(codigo__icontains=location).values_list("id_ubicacion", flat=True)
        details = details.filter(Q(id_ubicacion_origen__in=location_ids) | Q(id_ubicacion_destino__in=location_ids))
    if product or client or location:
        query = query.filter(id_movimiento__in=details.values_list("id_movimiento", flat=True))
    return serialize_movements(query[:500])


def traceability_report(term="", lot_term="", client_term=""):
    products = Producto.objects.filter(estado=True)
    if term:
        products = products.filter(Q(sku__icontains=term) | Q(codigo_ean__icontains=term) | Q(nombre__icontains=term))
    if client_term:
        client_ids = Cliente.objects.filter(Q(razon_social__icontains=client_term) | Q(ruc__icontains=client_term)).values_list("id_cliente", flat=True)
        products = products.filter(id_cliente__in=client_ids)
    if lot_term:
        products = products.filter(
            id_producto__in=Lote.objects.filter(
                codigo__icontains=lot_term
            ).values_list("id_producto", flat=True)
        )
    product_rows = list(products.order_by("nombre")[:30])
    clients = {item.id_cliente: item for item in Cliente.objects.filter(id_cliente__in={item.id_cliente for item in product_rows})}

    result = []
    for product in product_rows:
        client = clients.get(product.id_cliente)
        lots = list(Lote.objects.filter(id_producto=product.id_producto).order_by("fecha_vencimiento"))
        if lot_term:
            lots = [item for item in lots if lot_term.lower() in item.codigo.lower()]
        lot_ids = [item.id_lote for item in lots]
        events = []

        receipt_details = list(PedidoIngresoDetalle.objects.filter(id_producto=product.id_producto))
        receipt_ids = [item.id_pedido_ingreso for item in receipt_details]
        receipts = {item.id_pedido_ingreso: item for item in PedidoIngreso.objects.filter(id_pedido_ingreso__in=receipt_ids)}
        declared = defaultdict(list)
        for item in PedidoIngresoLote.objects.filter(id_pedido_ingreso_detalle__in=[row.id_pedido_ingreso_detalle for row in receipt_details]):
            if not lot_ids or item.id_lote in lot_ids:
                declared[item.id_pedido_ingreso_detalle].append(item)
        for detail in receipt_details:
            receipt = receipts.get(detail.id_pedido_ingreso)
            if not receipt:
                continue
            matching_lots = declared[detail.id_pedido_ingreso_detalle]
            if lot_term and not matching_lots:
                continue
            events.append({
                "tipo": "RECEPCION", "fecha": receipt.fecha_recepcion or receipt.fecha_registro,
                "titulo": f"Recepción {receipt.codigo_documento}", "documento": receipt.codigo_documento,
                "cantidad": detail.cantidad_recibida,
                "detalle": f"{receipt.estado} · {', '.join(next((lot.codigo for lot in lots if lot.id_lote == row.id_lote), '') for row in matching_lots) or 'sin lote'}",
            })

        stocks = list(Stock.objects.filter(id_producto=product.id_producto, id_lote__in=lot_ids) if lot_ids else Stock.objects.filter(id_producto=product.id_producto))
        stock_ids = [item.id_stock for item in stocks]
        serialized_stock = serialize_stocks(stocks)
        details = list(MovimientoDetalle.objects.filter(id_stock_origen__in=stock_ids))
        movements = {item.id_movimiento: item for item in Movimiento.objects.filter(id_movimiento__in=[row.id_movimiento for row in details])}
        locations = {item.id_ubicacion: item for item in Ubicacion.objects.filter(id_ubicacion__in={value for row in details for value in (row.id_ubicacion_origen, row.id_ubicacion_destino)})}
        for detail in details:
            movement = movements.get(detail.id_movimiento)
            if movement:
                origin = locations.get(detail.id_ubicacion_origen)
                destination = locations.get(detail.id_ubicacion_destino)
                events.append({
                    "tipo": "MOVIMIENTO", "fecha": movement.fecha_confirmacion or movement.fecha_registro,
                    "titulo": f"{movement.tipo_movimiento.title()} interno", "documento": f"MOV-{movement.id_movimiento}",
                    "cantidad": detail.cantidad, "detalle": f"{origin.codigo if origin else '-'} → {destination.codigo if destination else '-'} · {movement.estado}",
                })

        order_details = list(PedidoDetalle.objects.filter(id_producto=product.id_producto))
        if lot_term:
            order_details = [item for item in order_details if item.id_lote in lot_ids]
        orders = {item.id_pedido_salida: item for item in PedidoSalida.objects.filter(id_pedido_salida__in=[row.id_pedido_salida for row in order_details])}
        for detail in order_details:
            order = orders.get(detail.id_pedido_salida)
            if order:
                events.append({
                    "tipo": "DESPACHO", "fecha": order.fecha_despacho or order.fecha_registro,
                    "titulo": f"Pedido de salida {order.codigo_documento}", "documento": order.codigo_documento,
                    "cantidad": detail.cantidad_despachada, "detalle": order.estado,
                })

        product_order_ids = {item.id_pedido_salida for item in order_details}
        product_dispatches = list(Despacho.objects.filter(id_pedido_salida__in=product_order_ids))
        product_dispatch_ids = [item.id_despacho for item in product_dispatches]
        dispatch_details = list(DespachoDetalle.objects.filter(id_despacho__in=product_dispatch_ids))
        picking_details = {
            item.id_picking_detalle: item
            for item in PickingDetalle.objects.filter(
                id_picking_detalle__in=[row.id_picking_detalle for row in dispatch_details]
            )
        }
        reservations = {
            item.id_reserva: item
            for item in Reserva.objects.filter(
                id_reserva__in=[row.id_reserva for row in picking_details.values()]
            )
        }
        product_dispatch_detail_ids = []
        for dispatch_detail in dispatch_details:
            picking_detail = picking_details.get(dispatch_detail.id_picking_detalle)
            reservation = reservations.get(picking_detail.id_reserva) if picking_detail else None
            if reservation and reservation.id_stock in stock_ids:
                product_dispatch_detail_ids.append(dispatch_detail.id_despacho_detalle)
        for incident in IncidenciaDespacho.objects.filter(
            id_despacho_detalle__in=product_dispatch_detail_ids
        ):
            events.append({
                "tipo": "INCIDENCIA",
                "fecha": incident.fecha_registro,
                "titulo": f"Incidencia de despacho: {incident.tipo}",
                "documento": f"INC-D-{incident.id_incidencia_despacho}",
                "cantidad": incident.cantidad,
                "detalle": incident.descripcion or "Incidencia registrada en la salida.",
            })

        receipt_detail_ids = [item.id_pedido_ingreso_detalle for item in receipt_details]
        for incident in IncidenciaRecepcion.objects.filter(id_pedido_ingreso_detalle__in=receipt_detail_ids):
            events.append({"tipo": "INCIDENCIA", "fecha": incident.fecha_registro, "titulo": f"Incidencia de recepción: {incident.tipo}", "documento": f"INC-R-{incident.id_incidencia}", "cantidad": incident.cantidad_afectada, "detalle": incident.descripcion})

        events.sort(key=lambda item: item["fecha"] or timezone.now())
        result.append({
            "producto": {"id_producto": product.id_producto, "sku": product.sku, "nombre": product.nombre, "codigo_ean": product.codigo_ean},
            "cliente": {"id_cliente": client.id_cliente, "razon_social": client.razon_social, "ruc": client.ruc} if client else None,
            "lotes": [{"id_lote": item.id_lote, "codigo": item.codigo, "fecha_vencimiento": item.fecha_vencimiento} for item in lots],
            "stock_actual": serialized_stock,
            "eventos": events,
        })
    return result


def export_dataset(report_type, filters):
    if report_type == "inventario":
        rows = serialize_stocks(Stock.objects.all().order_by("-fecha_actualizacion")[:1000])
        return "Inventario", ["SKU", "Producto", "Cliente", "Almacén", "Ubicación", "Lote", "Total", "Reservado", "Disponible"], [[item["producto"]["sku"] if item["producto"] else "", item["producto"]["nombre"] if item["producto"] else "", item["cliente"]["razon_social"] if item["cliente"] else "", item["almacen"]["nombre"] if item["almacen"] else "", item["ubicacion"]["codigo"] if item["ubicacion"] else "", item["lote"]["codigo"] if item["lote"] else "", decimal_text(item["cantidad_total"]), decimal_text(item["cantidad_reservada"]), decimal_text(item["cantidad_disponible"])] for item in rows]
    if report_type == "recepciones":
        rows = serialize_receipts(PedidoIngreso.objects.all().order_by("-fecha_registro")[:1000])
        return "Recepciones", ["Documento", "Cliente", "Estado", "Programada", "Recepción", "Esperada", "Recibida", "Incidencias"], [[item["codigo_documento"], item["cliente"]["razon_social"] if item["cliente"] else "", item["estado"], item["fecha_programada"], item["fecha_recepcion"], decimal_text(item["cantidad_esperada"]), decimal_text(item["cantidad_recibida"]), item["cantidad_incidencias"]] for item in rows]
    if report_type == "movimientos":
        rows = movement_report(filters)
        return "Movimientos", ["ID", "Tipo", "Estado", "Fecha", "Responsable", "Cantidad", "Origen", "Destino"], [[item["id_movimiento"], item["tipo"], item["estado"], item["fecha_registro"], f'{item["responsable_registro"]["nombre"]} {item["responsable_registro"]["apellido"]}' if item["responsable_registro"] else "", decimal_text(item["cantidad_total"]), item["lineas"][0]["origen"]["codigo"] if item["lineas"] and item["lineas"][0]["origen"] else "", item["lineas"][0]["destino"]["codigo"] if item["lineas"] and item["lineas"][0]["destino"] else ""] for item in rows]
    if report_type == "despachos":
        rows = serialize_orders(PedidoSalida.objects.all().order_by("-fecha_registro")[:1000])
        return "Despachos", ["Documento", "Cliente", "Estado", "Programada", "Despacho", "Solicitado", "Despachado"], [[item["codigo_documento"], item["cliente"]["razon_social"] if item["cliente"] else "", item["estado"], item["fecha_programada"], item["fecha_despacho"], decimal_text(item["cantidad_solicitada"]), decimal_text(item["cantidad_despachada"])] for item in rows]
    if report_type == "ocupacion":
        rows = occupancy_report(filters.get("almacen", ""))
        return "Ocupación", ["Almacén", "Capacidad", "Utilizada", "Disponible", "% ocupación", "Ubicaciones ocupadas", "Ubicaciones libres"], [[item["nombre"], item["capacidad"], item["utilizada"], item["disponible"], item["porcentaje"], item["ubicaciones_ocupadas"], item["ubicaciones_libres"]] for item in rows]
    if report_type == "trazabilidad":
        rows = traceability_report(filters.get("producto", ""), filters.get("lote", ""), filters.get("cliente", ""))
        flattened = []
        for item in rows:
            for event in item["eventos"]:
                flattened.append([item["producto"]["sku"], item["producto"]["nombre"], item["cliente"]["razon_social"] if item["cliente"] else "", event["tipo"], event["fecha"], event["documento"], decimal_text(event["cantidad"]), event["detalle"]])
        return "Trazabilidad", ["SKU", "Producto", "Cliente", "Evento", "Fecha", "Documento", "Cantidad", "Detalle"], flattened
    raise ValueError("Tipo de reporte no soportado.")
