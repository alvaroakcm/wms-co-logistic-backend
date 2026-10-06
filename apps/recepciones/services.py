from collections import defaultdict
from decimal import Decimal

from django.db.models import Sum

from apps.inventario.models import AsignacionUbicacion, Lote, Stock
from apps.maestros.models import (
    Almacen,
    Cliente,
    Producto,
    Ubicacion,
    UnidadMedida,
    Zona,
)
from apps.usuarios.models import Usuario

from .models import (
    Discrepancia,
    IncidenciaRecepcion,
    PedidoIngreso,
    PedidoIngresoDetalle,
    PedidoIngresoLote,
)


def _user_data(user):
    if user is None:
        return None
    return {
        "id_usuario": user.id_usuario,
        "nombre": user.nombre,
        "apellido": user.apellido,
        "correo": user.correo,
    }


def serialize_receipts(receipts):
    receipts = list(receipts)
    receipt_ids = [item.id_pedido_ingreso for item in receipts]
    details = list(
        PedidoIngresoDetalle.objects.filter(
            id_pedido_ingreso__in=receipt_ids
        ).order_by("id_pedido_ingreso_detalle")
    )
    details_by_receipt = defaultdict(list)
    for detail in details:
        details_by_receipt[detail.id_pedido_ingreso].append(detail)
    discrepancy_counts = {
        row["id_pedido_ingreso"]: row["total"]
        for row in Discrepancia.objects.filter(
            id_pedido_ingreso__in=receipt_ids
        ).values("id_pedido_ingreso").annotate(total=Sum("cantidad"))
    }
    incident_counts = defaultdict(int)
    for receipt_id in IncidenciaRecepcion.objects.filter(
        id_pedido_ingreso__in=receipt_ids
    ).values_list("id_pedido_ingreso", flat=True):
        incident_counts[receipt_id] += 1
    clients = {
        item.id_cliente: item
        for item in Cliente.objects.filter(
            id_cliente__in={receipt.id_cliente for receipt in receipts}
        )
    }
    users = {
        str(item.id_usuario): item
        for item in Usuario.objects.filter(
            id_usuario__in={receipt.id_usuario_registro for receipt in receipts}
        )
    }

    result = []
    for receipt in receipts:
        receipt_details = details_by_receipt[receipt.id_pedido_ingreso]
        client = clients.get(receipt.id_cliente)
        result.append(
            {
                "id_pedido_ingreso": receipt.id_pedido_ingreso,
                "codigo_documento": receipt.codigo_documento,
                "id_cliente": receipt.id_cliente,
                "cliente": (
                    {
                        "id_cliente": client.id_cliente,
                        "razon_social": client.razon_social,
                        "ruc": client.ruc,
                    }
                    if client
                    else None
                ),
                "fecha_programada": receipt.fecha_programada,
                "fecha_recepcion": receipt.fecha_recepcion,
                "transporte_placa": receipt.transporte_placa or "",
                "transporte_conductor": receipt.transporte_conductor or "",
                "transporte_brevete": receipt.transporte_brevete or "",
                "estado": receipt.estado,
                "responsable": _user_data(
                    users.get(str(receipt.id_usuario_registro))
                ),
                "cantidad_lineas": len(receipt_details),
                "cantidad_esperada": sum(
                    (item.cantidad_esperada for item in receipt_details),
                    Decimal("0"),
                ),
                "cantidad_recibida": sum(
                    (item.cantidad_recibida for item in receipt_details),
                    Decimal("0"),
                ),
                "cantidad_discrepancia": discrepancy_counts.get(
                    receipt.id_pedido_ingreso, Decimal("0")
                ),
                "cantidad_incidencias": incident_counts[
                    receipt.id_pedido_ingreso
                ],
                "fecha_registro": receipt.fecha_registro,
                "fecha_actualizacion": receipt.fecha_actualizacion,
            }
        )
    return result


def serialize_receipt_detail(receipt):
    result = serialize_receipts([receipt])[0]
    details = list(
        PedidoIngresoDetalle.objects.filter(
            id_pedido_ingreso=receipt.id_pedido_ingreso
        ).order_by("id_pedido_ingreso_detalle")
    )
    products = {
        item.id_producto: item
        for item in Producto.objects.filter(
            id_producto__in={detail.id_producto for detail in details}
        )
    }
    units = {
        item.id_unidad_medida: item
        for item in UnidadMedida.objects.filter(
            id_unidad_medida__in={detail.id_unidad_medida for detail in details}
        )
    }
    declared_lots = list(
        PedidoIngresoLote.objects.filter(
            id_pedido_ingreso_detalle__in={
                detail.id_pedido_ingreso_detalle for detail in details
            }
        ).order_by("id_pedido_ingreso_lote")
    )
    lots = {
        item.id_lote: item
        for item in Lote.objects.filter(
            id_lote__in={item.id_lote for item in declared_lots}
        )
    }
    lots_by_detail = defaultdict(list)
    for declared in declared_lots:
        lot = lots.get(declared.id_lote)
        if lot:
            lots_by_detail[declared.id_pedido_ingreso_detalle].append(
                {
                    "id_pedido_ingreso_lote": (
                        declared.id_pedido_ingreso_lote
                    ),
                    "id_lote": lot.id_lote,
                    "codigo": lot.codigo,
                    "fecha_fabricacion": lot.fecha_fabricacion,
                    "fecha_vencimiento": lot.fecha_vencimiento,
                    "cantidad": declared.cantidad,
                }
            )
    discrepancies = defaultdict(list)
    for item in Discrepancia.objects.filter(
        id_pedido_ingreso=receipt.id_pedido_ingreso
    ).order_by("fecha_registro"):
        discrepancies[item.id_pedido_ingreso_detalle].append(
            {
                "id_discrepancia": item.id_discrepancia,
                "tipo": item.tipo,
                "cantidad": item.cantidad,
                "descripcion": item.descripcion or "",
                "fecha_registro": item.fecha_registro,
            }
        )

    assignments = defaultdict(list)
    assignment_rows = list(
        AsignacionUbicacion.objects.filter(
            id_pedido_ingreso=receipt.id_pedido_ingreso
        ).order_by("fecha_asignacion")
    )
    stocks = {
        item.id_stock: item
        for item in Stock.objects.filter(
            id_stock__in={row.id_stock for row in assignment_rows}
        )
    }
    assignment_lots = {
        item.id_lote: item
        for item in Lote.objects.filter(
            id_lote__in={
                stock.id_lote
                for stock in stocks.values()
                if stock.id_lote is not None
            }
        )
    }
    locations = {
        item.id_ubicacion: item
        for item in Ubicacion.objects.filter(
            id_ubicacion__in={row.id_ubicacion for row in assignment_rows}
        )
    }
    for assignment in assignment_rows:
        stock = stocks.get(assignment.id_stock)
        location = locations.get(assignment.id_ubicacion)
        if stock is None:
            continue
        assignments[stock.id_producto].append(
            {
                "id_asignacion": assignment.id_asignacion_ubicacion,
                "cantidad": assignment.cantidad,
                "fecha_asignacion": assignment.fecha_asignacion,
                "ubicacion": (
                    {
                        "id_ubicacion": location.id_ubicacion,
                        "codigo": location.codigo,
                    }
                    if location
                    else None
                ),
                "lote": (
                    {
                        "id_lote": assignment_lots[stock.id_lote].id_lote,
                        "codigo": assignment_lots[stock.id_lote].codigo,
                        "fecha_vencimiento": assignment_lots[
                            stock.id_lote
                        ].fecha_vencimiento,
                    }
                    if stock.id_lote in assignment_lots
                    else None
                ),
            }
        )

    result["lineas"] = []
    for detail in details:
        product = products.get(detail.id_producto)
        unit = units.get(detail.id_unidad_medida)
        result["lineas"].append(
            {
                "id_pedido_ingreso_detalle": detail.id_pedido_ingreso_detalle,
                "id_producto": detail.id_producto,
                "producto": (
                    {
                        "id_producto": product.id_producto,
                        "sku": product.sku,
                        "nombre": product.nombre,
                    }
                    if product
                    else None
                ),
                "codigo_producto": detail.codigo_producto,
                "descripcion_producto": detail.descripcion_producto,
                "controla_lote": product.controla_lote if product else False,
                "cantidad_pallets": detail.cantidad_pallets,
                "factor_conversion": detail.factor_conversion,
                "cantidad_cajas": (
                    detail.cantidad_pallets * detail.factor_conversion
                    if detail.factor_conversion is not None
                    else None
                ),
                "id_unidad_medida": detail.id_unidad_medida,
                "unidad_medida": (
                    {"codigo": unit.codigo, "nombre": unit.nombre}
                    if unit
                    else None
                ),
                "cantidad_esperada": detail.cantidad_esperada,
                "cantidad_recibida": detail.cantidad_recibida,
                "cantidad_rechazada": detail.cantidad_rechazada,
                "discrepancias": discrepancies[
                    detail.id_pedido_ingreso_detalle
                ],
                "asignaciones": assignments[detail.id_producto],
                "lotes": lots_by_detail[
                    detail.id_pedido_ingreso_detalle
                ],
            }
        )

    incident_users = {
        str(item.id_usuario): item
        for item in Usuario.objects.filter(
            id_usuario__in=IncidenciaRecepcion.objects.filter(
                id_pedido_ingreso=receipt.id_pedido_ingreso
            ).values_list("id_usuario_responsable", flat=True)
        )
    }
    result["incidencias"] = [
        {
            "id_incidencia": item.id_incidencia,
            "id_pedido_ingreso_detalle": item.id_pedido_ingreso_detalle,
            "tipo": item.tipo,
            "descripcion": item.descripcion,
            "cantidad_afectada": item.cantidad_afectada,
            "responsable": _user_data(
                incident_users.get(str(item.id_usuario_responsable))
            ),
            "fecha_registro": item.fecha_registro,
        }
        for item in IncidenciaRecepcion.objects.filter(
            id_pedido_ingreso=receipt.id_pedido_ingreso
        ).order_by("-fecha_registro")
    ]
    return result


def available_locations():
    occupied_ids = Stock.objects.filter(cantidad_total__gt=0).values_list(
        "id_ubicacion", flat=True
    )
    locations = list(
        Ubicacion.objects.filter(estado=True)
        .exclude(id_ubicacion__in=occupied_ids)
        .order_by("codigo")
    )
    zones = {
        item.id_zona: item
        for item in Zona.objects.filter(
            id_zona__in={location.id_zona for location in locations}, estado=True
        )
    }
    warehouses = {
        item.id_almacen: item
        for item in Almacen.objects.filter(
            id_almacen__in={zone.id_almacen for zone in zones.values()},
            estado=True,
        )
    }
    return [
        {
            "id_ubicacion": location.id_ubicacion,
            "codigo": location.codigo,
            "pasillo": location.pasillo,
            "rack": location.rack,
            "nivel": location.nivel,
            "posicion": location.posicion,
            "zona": zones.get(location.id_zona).nombre
            if zones.get(location.id_zona)
            else None,
            "almacen": warehouses.get(zones[location.id_zona].id_almacen).nombre
            if location.id_zona in zones
            and zones[location.id_zona].id_almacen in warehouses
            else None,
        }
        for location in locations
        if location.id_zona in zones
    ]
