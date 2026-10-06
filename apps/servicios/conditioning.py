from decimal import Decimal

from apps.inventario.models import Stock
from apps.inventario.services import serialize_stocks
from apps.maestros.models import Cliente
from apps.usuarios.models import Usuario

from .models import Reencajado, Repaletizado, Servicio


def serialize_services(queryset):
    services = list(queryset)
    ids = [item.id_servicio for item in services]
    clients = {
        item.id_cliente: item
        for item in Cliente.objects.filter(id_cliente__in={item.id_cliente for item in services})
    }
    repallets = {
        item.id_servicio: item
        for item in Repaletizado.objects.filter(id_servicio__in=ids)
    }
    reboxings = {
        item.id_servicio: item
        for item in Reencajado.objects.filter(id_servicio__in=ids)
    }
    stock_ids = {item.id_stock for item in [*repallets.values(), *reboxings.values()]}
    stocks = list(Stock.objects.filter(id_stock__in=stock_ids))
    stock_data = {item["id_stock"]: item for item in serialize_stocks(stocks)}
    user_ids = {
        value
        for item in services
        for value in (item.id_usuario_registro, item.id_usuario_ejecucion)
        if value
    }
    users = {
        str(item.id_usuario): item
        for item in Usuario.objects.filter(id_usuario__in=user_ids)
    }
    result = []
    for service in services:
        repallet = repallets.get(service.id_servicio)
        reboxing = reboxings.get(service.id_servicio)
        detail = repallet or reboxing
        stock = stock_data.get(detail.id_stock) if detail else None
        client = clients.get(service.id_cliente)
        register_user = users.get(str(service.id_usuario_registro))
        execution_user = users.get(str(service.id_usuario_ejecucion))
        units = repallet.cantidad_pallets if repallet else service.cantidad
        total = Decimal(service.tarifa_aplicada or 0) * Decimal(units or 0)
        detail_data = None
        if repallet:
            detail_data = {
                "id_repaletizado": repallet.id_repaletizado,
                "id_stock": repallet.id_stock,
                "id_pallet_origen": repallet.id_pallet_origen,
                "id_pallet_destino": repallet.id_pallet_destino,
                "codigo_pallet_destino": repallet.codigo_pallet_destino,
                "numero_paletas": repallet.cantidad_pallets,
                "cliente_provee_pallet_destino": repallet.cliente_provee_pallet_destino,
                "tipo_pallet_destino": repallet.tipo_pallet_destino,
                "certificacion_destino": repallet.certificacion_destino,
            }
        elif reboxing:
            detail_data = {
                "id_reencajado": reboxing.id_reencajado,
                "id_stock": reboxing.id_stock,
                "cantidad_cajas_origen": reboxing.cantidad_cajas_origen,
                "cantidad_cajas_destino": reboxing.cantidad_cajas_destino,
            }
        result.append({
            "id_servicio": service.id_servicio,
            "codigo": service.codigo,
            "tipo": service.tipo_servicio,
            "estado": service.estado,
            "descripcion": service.descripcion,
            "cantidad": service.cantidad,
            "facturable": service.facturable,
            "estado_facturacion": service.estado_facturacion,
            "tarifa": service.tarifa_aplicada,
            "unidad_facturacion": "PALLET" if repallet else "UNIDAD",
            "unidades_facturables": units,
            "importe_total": total,
            "cliente": {
                "id_cliente": client.id_cliente,
                "razon_social": client.razon_social,
                "ruc": client.ruc,
            } if client else None,
            "stock": stock,
            "detalle": detail_data,
            "responsable_solicitud": {
                "nombre": register_user.nombre,
                "apellido": register_user.apellido,
                "correo": register_user.correo,
            } if register_user else None,
            "responsable_ejecucion": {
                "nombre": execution_user.nombre,
                "apellido": execution_user.apellido,
                "correo": execution_user.correo,
            } if execution_user else None,
            "fecha_solicitud": service.fecha_servicio,
            "fecha_ejecucion": service.fecha_ejecucion,
            "fecha_reporte": service.fecha_reporte,
            "observaciones": service.observaciones,
        })
    return result


def billing_rows(services):
    data = serialize_services(services)
    headers = ["Código", "Tipo", "Cliente", "RUC", "Descripción", "Cantidad", "Unidad facturable", "Unidades", "Tarifa", "Importe", "Estado facturación", "Ejecución"]
    rows = [
        [
            item["codigo"], item["tipo"], item["cliente"]["razon_social"] if item["cliente"] else "",
            item["cliente"]["ruc"] if item["cliente"] else "", item["descripcion"], item["cantidad"],
            item["unidad_facturacion"], item["unidades_facturables"], item["tarifa"], item["importe_total"],
            item["estado_facturacion"], item["fecha_ejecucion"],
        ]
        for item in data
    ]
    return headers, rows
