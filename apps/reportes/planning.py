from collections import Counter, defaultdict
from datetime import timedelta
from decimal import Decimal, ROUND_CEILING

from django.db.models import Q
from django.utils import timezone

from apps.inventario.models import AsignacionUbicacion, Reserva, Stock
from apps.maestros.models import Almacen, Cliente, Producto, ProductoConversion, Ubicacion, UnidadMedida, Zona
from apps.pedidos.models import PedidoDetalle, PedidoSalida, Picking, PickingDetalle
from apps.recepciones.models import PedidoIngreso, PedidoIngresoDetalle

from .services import occupancy_report


def _ceil(value):
    return int(Decimal(value).quantize(Decimal("1"), rounding=ROUND_CEILING))


def _build_series(capacity, baseline, events, date_from, date_to, threshold, today=None):
    """Pure projection engine used by the API and unit tests."""
    today = today or timezone.localdate()
    planned = baseline
    actual = baseline
    rows = []
    risk_periods = []
    for index in range((date_to - date_from).days + 1):
        date = date_from + timedelta(days=index)
        event = events.get(date, {})
        planned = max(planned + event.get("planned_in", 0) - event.get("planned_out", 0), 0)
        actual = max(actual + event.get("actual_in", 0) - event.get("actual_out", 0), 0)
        planned_percentage = round((planned / capacity) * 100, 2) if capacity else 0
        actual_percentage = round((actual / capacity) * 100, 2) if capacity else 0
        row = {
            "fecha": date,
            "ingresos_programados": event.get("planned_in", 0),
            "salidas_programadas": event.get("planned_out", 0),
            "ingresos_reales": event.get("actual_in", 0),
            "salidas_reales": event.get("actual_out", 0),
            "ocupacion_planificada": planned,
            "porcentaje_planificado": planned_percentage,
            "ocupacion_real": actual if date <= today else None,
            "porcentaje_real": actual_percentage if date <= today else None,
            "diferencia": actual - planned if date <= today else None,
        }
        rows.append(row)
        if planned_percentage >= threshold:
            risk_periods.append({
                "fecha": date,
                "porcentaje": planned_percentage,
                "ocupacion": planned,
                "capacidad": capacity,
                "nivel": "SATURADO" if planned_percentage >= 100 else "CRITICO" if planned_percentage >= 95 else "ALERTA",
            })
    return rows, risk_periods


def _pallet_factors(product_ids):
    pallet_unit = UnidadMedida.objects.filter(codigo__iexact="PLT", estado=True).first()
    if not pallet_unit:
        return {}
    return {
        item.id_producto: item.factor_conversion
        for item in ProductoConversion.objects.filter(
            id_producto__in=product_ids,
            id_unidad_origen=pallet_unit.id_unidad_medida,
        )
        if item.factor_conversion > 0
    }


def _warehouse_maps():
    warehouses = list(Almacen.objects.filter(estado=True).order_by("nombre"))
    zones = {item.id_zona: item for item in Zona.objects.filter(id_almacen__in=[row.id_almacen for row in warehouses])}
    locations = {item.id_ubicacion: item for item in Ubicacion.objects.filter(id_zona__in=list(zones))}
    location_warehouse = {
        location_id: zones[location.id_zona].id_almacen
        for location_id, location in locations.items()
        if location.id_zona in zones
    }
    stock_rows = list(Stock.objects.filter(id_ubicacion__in=list(location_warehouse)))
    stock_warehouse = {item.id_stock: location_warehouse.get(item.id_ubicacion) for item in stock_rows}
    product_counts = defaultdict(Counter)
    for stock in stock_rows:
        if stock.cantidad_total > 0 and stock_warehouse.get(stock.id_stock):
            product_counts[stock.id_producto][stock_warehouse[stock.id_stock]] += float(stock.cantidad_total)
    default_warehouse = warehouses[0].id_almacen if warehouses else None
    primary = {
        product_id: counts.most_common(1)[0][0]
        for product_id, counts in product_counts.items()
    }
    return warehouses, stock_rows, stock_warehouse, primary, default_warehouse


def capacity_plan(date_from, date_to, warehouse_term="", client_term="", threshold=85):
    warehouses, stocks, stock_warehouse, product_primary, default_warehouse = _warehouse_maps()
    if warehouse_term:
        warehouses = [
            item for item in warehouses
            if warehouse_term.lower() in item.nombre.lower()
            or warehouse_term.lower() in item.codigo.lower()
            or warehouse_term == str(item.id_almacen)
        ]
    warehouse_ids = {item.id_almacen for item in warehouses}
    if not warehouse_ids:
        return {"periodo": {"desde": date_from, "hasta": date_to}, "umbral": threshold, "almacenes": [], "alertas": [], "operaciones": []}

    client_ids = None
    if client_term:
        client_ids = set(Cliente.objects.filter(Q(razon_social__icontains=client_term) | Q(ruc__icontains=client_term)).values_list("id_cliente", flat=True))

    today = timezone.localdate()
    receipts_query = PedidoIngreso.objects.filter(
        Q(fecha_programada__range=(date_from, date_to))
        | Q(fecha_recepcion__date__range=(date_from, today))
    ).exclude(estado__iexact="Cancelado")
    orders_query = PedidoSalida.objects.filter(
        Q(fecha_programada__range=(date_from, date_to))
        | Q(fecha_despacho__date__range=(date_from, today))
    ).exclude(estado__iexact="Cancelado")
    if client_ids is not None:
        receipts_query = receipts_query.filter(id_cliente__in=client_ids)
        orders_query = orders_query.filter(id_cliente__in=client_ids)
    receipts = list(receipts_query)
    orders = list(orders_query)
    receipt_details = list(PedidoIngresoDetalle.objects.filter(id_pedido_ingreso__in=[item.id_pedido_ingreso for item in receipts]))
    order_details = list(PedidoDetalle.objects.filter(id_pedido_salida__in=[item.id_pedido_salida for item in orders]))
    product_ids = {item.id_producto for item in receipt_details} | {item.id_producto for item in order_details}
    factors = _pallet_factors(product_ids)
    products = {item.id_producto: item for item in Producto.objects.filter(id_producto__in=product_ids)}

    stock_product = {item.id_stock: item.id_producto for item in stocks}
    receipt_warehouse = defaultdict(list)
    assignments = list(AsignacionUbicacion.objects.filter(id_pedido_ingreso__in=[item.id_pedido_ingreso for item in receipts]))
    for assignment in assignments:
        warehouse_id = stock_warehouse.get(assignment.id_stock)
        if warehouse_id:
            receipt_warehouse[
                (assignment.id_pedido_ingreso, stock_product.get(assignment.id_stock))
            ].append(warehouse_id)

    pickings = {item.id_pedido_salida: item for item in Picking.objects.filter(id_pedido_salida__in=[row.id_pedido_salida for row in orders])}
    picking_details = list(PickingDetalle.objects.filter(id_picking__in=[item.id_picking for item in pickings.values()]))
    reservations = {item.id_reserva: item for item in Reserva.objects.filter(id_reserva__in=[row.id_reserva for row in picking_details])}
    reservation_warehouse_by_detail = defaultdict(list)
    for picking_detail in picking_details:
        reservation = reservations.get(picking_detail.id_reserva)
        if reservation:
            warehouse_id = stock_warehouse.get(reservation.id_stock)
            if warehouse_id:
                reservation_warehouse_by_detail[reservation.id_pedido_detalle].append(warehouse_id)

    events = defaultdict(lambda: defaultdict(lambda: {"planned_in": 0, "planned_out": 0, "actual_in": 0, "actual_out": 0}))
    operations = []
    receipt_map = {item.id_pedido_ingreso: item for item in receipts}
    for detail in receipt_details:
        receipt = receipt_map[detail.id_pedido_ingreso]
        candidate = receipt_warehouse.get(
            (receipt.id_pedido_ingreso, detail.id_producto)
        )
        warehouse_id = candidate[0] if candidate else product_primary.get(detail.id_producto, default_warehouse)
        if warehouse_id not in warehouse_ids:
            continue
        pallets = _ceil(detail.cantidad_pallets) if detail.cantidad_pallets > 0 else _ceil(detail.cantidad_esperada / factors[detail.id_producto]) if factors.get(detail.id_producto) else 1
        if date_from <= receipt.fecha_programada <= date_to:
            events[warehouse_id][receipt.fecha_programada]["planned_in"] += pallets
        if receipt.fecha_recepcion and date_from <= receipt.fecha_recepcion.date() <= today:
            events[warehouse_id][receipt.fecha_recepcion.date()]["actual_in"] += pallets
        if date_from <= receipt.fecha_programada <= date_to:
            operations.append({"tipo": "RECEPCION", "documento": receipt.codigo_documento, "fecha": receipt.fecha_programada, "almacen_id": warehouse_id, "producto": products.get(detail.id_producto).nombre if detail.id_producto in products else "Producto", "pallets": pallets, "estado": receipt.estado})

    order_map = {item.id_pedido_salida: item for item in orders}
    for detail in order_details:
        order = order_map[detail.id_pedido_salida]
        candidates = reservation_warehouse_by_detail.get(detail.id_pedido_detalle)
        warehouse_id = candidates[0] if candidates else product_primary.get(detail.id_producto, default_warehouse)
        if warehouse_id not in warehouse_ids:
            continue
        pallets = _ceil(detail.cantidad_solicitada / factors[detail.id_producto]) if factors.get(detail.id_producto) else 1
        if date_from <= order.fecha_programada <= date_to:
            events[warehouse_id][order.fecha_programada]["planned_out"] += pallets
        if order.fecha_despacho and date_from <= order.fecha_despacho.date() <= today:
            events[warehouse_id][order.fecha_despacho.date()]["actual_out"] += pallets
        if date_from <= order.fecha_programada <= date_to:
            operations.append({"tipo": "DESPACHO", "documento": order.codigo_documento, "fecha": order.fecha_programada, "almacen_id": warehouse_id, "producto": products.get(detail.id_producto).nombre if detail.id_producto in products else "Producto", "pallets": pallets, "estado": order.estado})

    occupancy = {item["id_almacen"]: item for item in occupancy_report()}
    client_usage = None
    if client_ids is not None:
        client_product_ids = set(
            Producto.objects.filter(id_cliente__in=client_ids).values_list(
                "id_producto", flat=True
            )
        )
        client_pallets = defaultdict(set)
        client_unpalletized_locations = defaultdict(set)
        for stock in stocks:
            warehouse_id = stock_warehouse.get(stock.id_stock)
            if (
                warehouse_id in warehouse_ids
                and stock.id_producto in client_product_ids
                and stock.cantidad_total > 0
            ):
                if stock.id_pallet:
                    client_pallets[warehouse_id].add(stock.id_pallet)
                else:
                    client_unpalletized_locations[warehouse_id].add(
                        stock.id_ubicacion
                    )
        client_usage = {
            warehouse_id: len(client_pallets[warehouse_id])
            + len(client_unpalletized_locations[warehouse_id])
            for warehouse_id in warehouse_ids
        }
    result = []
    all_alerts = []
    for warehouse in warehouses:
        current = occupancy.get(warehouse.id_almacen, {})
        current_used = (
            client_usage.get(warehouse.id_almacen, 0)
            if client_usage is not None
            else int(current.get("utilizada", 0))
        )
        warehouse_events = events[warehouse.id_almacen]
        actual_delta_to_today = sum(
            event["actual_in"] - event["actual_out"]
            for date, event in warehouse_events.items()
            if date_from <= date <= today
        )
        baseline = max(current_used - actual_delta_to_today, 0)
        series, risks = _build_series(warehouse.capacidad_pallets, baseline, warehouse_events, date_from, date_to, threshold)
        for risk in risks:
            all_alerts.append({**risk, "id_almacen": warehouse.id_almacen, "almacen": warehouse.nombre, "codigo": warehouse.codigo})
        result.append({
            "id_almacen": warehouse.id_almacen,
            "codigo": warehouse.codigo,
            "nombre": warehouse.nombre,
            "capacidad": warehouse.capacidad_pallets,
            "ocupacion_actual": current_used,
            "disponible_actual": max(warehouse.capacidad_pallets - current_used, 0),
            "porcentaje_actual": (
                round((current_used / warehouse.capacidad_pallets) * 100, 2)
                if warehouse.capacidad_pallets else 0
            ),
            "pico_planificado": max((row["porcentaje_planificado"] for row in series), default=0),
            "serie": series,
        })
    operations.sort(key=lambda item: (item["fecha"], item["tipo"], item["documento"]))
    all_alerts.sort(key=lambda item: (-item["porcentaje"], item["fecha"]))
    return {"periodo": {"desde": date_from, "hasta": date_to}, "umbral": threshold, "almacenes": result, "alertas": all_alerts, "operaciones": operations[:500]}
