from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.maestros.models import Almacen, Cliente, Pallet, Producto, Ubicacion, Zona
from apps.usuarios.permissions import require_application_permission

from .models import Lote, Movimiento, MovimientoDetalle, Stock
from .serializers import MovementCreateSerializer, RepackingSerializer
from .services import serialize_movements, serialize_stocks


def _date_param(request, name):
    value = request.query_params.get(name, "").strip()
    if not value:
        return None
    try:
        return timezone.datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValidationError(
            {name: ["La fecha debe utilizar el formato AAAA-MM-DD."]}
        ) from exc


def _filter_stock_queryset(request):
    query = Stock.objects.all().order_by("-fecha_actualizacion", "-id_stock")
    product = request.query_params.get("producto", "").strip()
    if product:
        product_ids = Producto.objects.filter(
            Q(sku__icontains=product)
            | Q(codigo_ean__icontains=product)
            | Q(nombre__icontains=product)
        ).values_list("id_producto", flat=True)
        query = query.filter(id_producto__in=product_ids)
    client = request.query_params.get("cliente", "").strip()
    if client:
        client_ids = Cliente.objects.filter(
            Q(razon_social__icontains=client) | Q(ruc__icontains=client)
        ).values_list("id_cliente", flat=True)
        product_ids = Producto.objects.filter(
            id_cliente__in=client_ids
        ).values_list("id_producto", flat=True)
        query = query.filter(id_producto__in=product_ids)
    warehouse = request.query_params.get("almacen", "").strip()
    location = request.query_params.get("ubicacion", "").strip()
    if warehouse or location:
        location_query = Ubicacion.objects.all()
        if location:
            location_query = location_query.filter(
                Q(codigo__icontains=location)
                | Q(pasillo__icontains=location)
                | Q(rack__icontains=location)
            )
        if warehouse:
            warehouse_ids = Almacen.objects.filter(
                Q(nombre__icontains=warehouse) | Q(codigo__icontains=warehouse)
            ).values_list("id_almacen", flat=True)
            zone_ids = Zona.objects.filter(
                id_almacen__in=warehouse_ids
            ).values_list("id_zona", flat=True)
            location_query = location_query.filter(id_zona__in=zone_ids)
        query = query.filter(
            id_ubicacion__in=location_query.values_list("id_ubicacion", flat=True)
        )
    stock_status = request.query_params.get("estado", "").strip().upper()
    if stock_status:
        query = query.filter(estado_stock=stock_status)
    lot = request.query_params.get("lote", "").strip()
    expiration = _date_param(request, "fecha_vencimiento")
    if lot or expiration:
        lot_query = Lote.objects.all()
        if lot:
            lot_query = lot_query.filter(codigo__icontains=lot)
        if expiration:
            lot_query = lot_query.filter(fecha_vencimiento=expiration)
        query = query.filter(
            id_lote__in=lot_query.values_list("id_lote", flat=True)
        )
    return query


class StockListView(APIView):
    def get(self, request):
        require_application_permission(request.user, "inventario.ver")
        return Response(serialize_stocks(_filter_stock_queryset(request)[:500]))


class InventoryOptionsView(APIView):
    def get(self, request):
        require_application_permission(request.user, "inventario.ver")
        warehouses = list(Almacen.objects.filter(estado=True).order_by("nombre"))
        zones = {
            item.id_zona: item
            for item in Zona.objects.filter(
                id_almacen__in=[item.id_almacen for item in warehouses]
            )
        }
        locations = list(Ubicacion.objects.filter(estado=True).order_by("codigo"))
        return Response(
            {
                "almacenes": [
                    {
                        "id_almacen": item.id_almacen,
                        "codigo": item.codigo,
                        "nombre": item.nombre,
                    }
                    for item in warehouses
                ],
                "ubicaciones": [
                    {
                        "id_ubicacion": item.id_ubicacion,
                        "codigo": item.codigo,
                        "id_almacen": (
                            zones[item.id_zona].id_almacen
                            if item.id_zona in zones
                            else None
                        ),
                    }
                    for item in locations
                ],
                "estados_stock": [
                    {"codigo": "DISP", "nombre": "Disponible"},
                    {"codigo": "RES", "nombre": "Reservado"},
                    {"codigo": "BLOQ", "nombre": "Bloqueado"},
                    {"codigo": "INV", "nombre": "En inventario"},
                ],
                "estados_movimiento": [
                    "PENDIENTE",
                    "CONFIRMADO",
                    "CANCELADO",
                ],
            }
        )


class OccupancyView(APIView):
    def get(self, request):
        require_application_permission(request.user, "inventario.ocupacion")
        warehouses = list(Almacen.objects.filter(estado=True).order_by("nombre"))
        zones = list(
            Zona.objects.filter(
                id_almacen__in=[item.id_almacen for item in warehouses],
                estado=True,
            )
        )
        zone_map = {item.id_zona: item for item in zones}
        locations = list(
            Ubicacion.objects.filter(
                id_zona__in=list(zone_map), estado=True
            ).order_by("codigo")
        )
        stocks = list(
            Stock.objects.filter(
                id_ubicacion__in=[item.id_ubicacion for item in locations],
                cantidad_total__gt=0,
            )
        )
        stocks_by_location = defaultdict(list)
        for stock in stocks:
            stocks_by_location[stock.id_ubicacion].append(stock)

        location_map = {item.id_ubicacion: item for item in locations}
        payload = []
        for warehouse in warehouses:
            warehouse_locations = [
                item
                for item in locations
                if zone_map[item.id_zona].id_almacen == warehouse.id_almacen
            ]
            occupied_pallets = set()
            unpalletized_locations = set()
            location_rows = []
            for location in warehouse_locations:
                location_stocks = stocks_by_location[location.id_ubicacion]
                pallet_ids = {
                    stock.id_pallet for stock in location_stocks if stock.id_pallet
                }
                occupied_pallets.update(pallet_ids)
                if location_stocks and not pallet_ids:
                    unpalletized_locations.add(location.id_ubicacion)
                location_rows.append(
                    {
                        "id_ubicacion": location.id_ubicacion,
                        "codigo": location.codigo,
                        "zona": zone_map[location.id_zona].nombre,
                        "ocupada": bool(location_stocks),
                        "pallets": len(pallet_ids) or (1 if location_stocks else 0),
                        "cantidad_stock": sum(
                            (item.cantidad_total for item in location_stocks),
                            Decimal("0"),
                        ),
                    }
                )
            used = len(occupied_pallets) + len(unpalletized_locations)
            capacity = max(warehouse.capacidad_pallets, 0)
            payload.append(
                {
                    "id_almacen": warehouse.id_almacen,
                    "codigo": warehouse.codigo,
                    "nombre": warehouse.nombre,
                    "capacidad": capacity,
                    "utilizada": used,
                    "disponible": max(capacity - used, 0),
                    "porcentaje": (
                        round((used / capacity) * 100, 2) if capacity else 0
                    ),
                    "ubicaciones": location_rows,
                }
            )
        return Response(payload)


class ExpirationAlertView(APIView):
    def get(self, request):
        require_application_permission(request.user, "inventario.vencimientos")
        try:
            days = int(request.query_params.get("dias", "30"))
        except ValueError as exc:
            raise ValidationError({"dias": ["Indica un número entero de días."]}) from exc
        if days < 0 or days > 3650:
            raise ValidationError({"dias": ["El umbral debe estar entre 0 y 3650 días."]})
        today = timezone.localdate()
        lot_query = Lote.objects.filter(
            fecha_vencimiento__isnull=False,
            fecha_vencimiento__lte=today + timedelta(days=days),
        )
        lot_codes = request.query_params.get("lote", "").strip()
        if lot_codes:
            lot_query = lot_query.filter(codigo__icontains=lot_codes)
        lot_ids = lot_query.values_list("id_lote", flat=True)
        stock_query = _filter_stock_queryset(request).filter(
            id_lote__in=lot_ids, cantidad_total__gt=0
        )
        serialized = serialize_stocks(stock_query[:500])
        for item in serialized:
            expiration = item["lote"]["fecha_vencimiento"]
            item["dias_restantes"] = (expiration - today).days
            item["nivel"] = (
                "VENCIDO"
                if item["dias_restantes"] < 0
                else "CRITICO"
                if item["dias_restantes"] <= 7
                else "PROXIMO"
            )
        serialized.sort(key=lambda item: item["lote"]["fecha_vencimiento"])
        return Response({"umbral_dias": days, "resultados": serialized})


class MovementListCreateView(APIView):
    def get(self, request):
        require_application_permission(request.user, "movimientos.ver")
        query = Movimiento.objects.all().order_by("-fecha_registro", "-id_movimiento")
        movement_status = request.query_params.get("estado", "").strip().upper()
        movement_type = request.query_params.get("tipo", "").strip().upper()
        if movement_status:
            query = query.filter(estado=movement_status)
        if movement_type:
            query = query.filter(tipo_movimiento=movement_type)

        date_from = _date_param(request, "fecha_desde")
        date_to = _date_param(request, "fecha_hasta")
        if date_from:
            query = query.filter(fecha_registro__date__gte=date_from)
        if date_to:
            query = query.filter(fecha_registro__date__lte=date_to)
        if date_from and date_to and date_from > date_to:
            raise ValidationError(
                {"fecha_hasta": ["La fecha final debe ser posterior a la inicial."]}
            )

        detail_query = MovimientoDetalle.objects.all()
        product = request.query_params.get("producto", "").strip()
        if product:
            product_ids = Producto.objects.filter(
                Q(sku__icontains=product) | Q(nombre__icontains=product)
            ).values_list("id_producto", flat=True)
            stock_ids = Stock.objects.filter(
                id_producto__in=product_ids
            ).values_list("id_stock", flat=True)
            detail_query = detail_query.filter(id_stock_origen__in=stock_ids)
        origin = request.query_params.get("origen", "").strip()
        destination = request.query_params.get("destino", "").strip()
        if origin:
            origin_ids = Ubicacion.objects.filter(
                codigo__icontains=origin
            ).values_list("id_ubicacion", flat=True)
            detail_query = detail_query.filter(id_ubicacion_origen__in=origin_ids)
        if destination:
            destination_ids = Ubicacion.objects.filter(
                codigo__icontains=destination
            ).values_list("id_ubicacion", flat=True)
            detail_query = detail_query.filter(
                id_ubicacion_destino__in=destination_ids
            )
        if product or origin or destination:
            query = query.filter(
                id_movimiento__in=detail_query.values_list(
                    "id_movimiento", flat=True
                )
            )
        responsible = request.query_params.get("responsable", "").strip()
        if responsible:
            from apps.usuarios.models import Usuario

            user_ids = Usuario.objects.filter(
                Q(nombre__icontains=responsible)
                | Q(apellido__icontains=responsible)
                | Q(correo__icontains=responsible)
            ).values_list("id_usuario", flat=True)
            query = query.filter(
                Q(id_usuario_registro__in=user_ids)
                | Q(id_usuario_confirma__in=user_ids)
            )
        return Response(serialize_movements(query[:500]))

    def post(self, request):
        require_application_permission(request.user, "movimientos.crear")
        serializer = MovementCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        now = timezone.now()
        with transaction.atomic():
            stock_ids = [item["id_stock_origen"] for item in data["lineas"]]
            stocks = {
                item.id_stock: item
                for item in Stock.objects.select_for_update().filter(
                    id_stock__in=stock_ids
                )
            }
            locations = {
                item.id_ubicacion
                for item in Ubicacion.objects.filter(
                    id_ubicacion__in=[
                        item["id_ubicacion_destino"] for item in data["lineas"]
                    ],
                    estado=True,
                )
            }
            requested_pallet_ids = {
                item["id_pallet_destino"]
                for item in data["lineas"]
                if item["id_pallet_destino"]
            }
            valid_pallet_ids = set(
                Pallet.objects.filter(
                    id_pallet__in=requested_pallet_ids
                ).values_list("id_pallet", flat=True)
            )
            errors = []
            for line in data["lineas"]:
                stock = stocks.get(line["id_stock_origen"])
                if not stock:
                    errors.append("Uno de los stocks de origen no existe.")
                    continue
                if line["id_ubicacion_destino"] not in locations:
                    errors.append("Una ubicación de destino no existe o está inactiva.")
                if line["id_ubicacion_destino"] == stock.id_ubicacion:
                    errors.append("El origen y el destino deben ser diferentes.")
                if (
                    line["id_pallet_destino"]
                    and line["id_pallet_destino"] not in valid_pallet_ids
                ):
                    errors.append("El pallet de destino no existe.")
                if line["cantidad"] > stock.cantidad_total - stock.cantidad_reservada:
                    errors.append(
                        f"El stock {stock.id_stock} no tiene cantidad disponible suficiente."
                    )
            if errors:
                raise ValidationError({"lineas": errors})
            movement = Movimiento.objects.create(
                tipo_movimiento="TRASLADO",
                motivo=data["motivo"] or "Traslado interno",
                estado="PENDIENTE",
                id_usuario_registro=request.user.id,
                fecha_registro=now,
                fecha_actualizacion=now,
            )
            MovimientoDetalle.objects.bulk_create(
                [
                    MovimientoDetalle(
                        id_movimiento=movement.id_movimiento,
                        id_stock_origen=line["id_stock_origen"],
                        id_ubicacion_origen=stocks[
                            line["id_stock_origen"]
                        ].id_ubicacion,
                        id_ubicacion_destino=line["id_ubicacion_destino"],
                        id_pallet_destino=line["id_pallet_destino"],
                        cantidad=line["cantidad"],
                    )
                    for line in data["lineas"]
                ]
            )
        return Response(
            serialize_movements([movement])[0], status=status.HTTP_201_CREATED
        )


class MovementConfirmView(APIView):
    def post(self, request, movement_id):
        require_application_permission(request.user, "movimientos.confirmar")
        with transaction.atomic():
            movement = get_object_or_404(
                Movimiento.objects.select_for_update(),
                id_movimiento=movement_id,
            )
            if movement.estado != "PENDIENTE":
                raise ValidationError(
                    {"estado": ["Solo se pueden confirmar movimientos pendientes."]}
                )
            details = list(
                MovimientoDetalle.objects.select_for_update().filter(
                    id_movimiento=movement_id
                )
            )
            source_stocks = {
                item.id_stock: item
                for item in Stock.objects.select_for_update().filter(
                    id_stock__in=[item.id_stock_origen for item in details]
                )
            }
            now = timezone.now()
            for detail in details:
                source = source_stocks.get(detail.id_stock_origen)
                if not source:
                    raise ValidationError(
                        {"stock": ["El stock de origen ya no existe."]}
                    )
                available = source.cantidad_total - source.cantidad_reservada
                if detail.cantidad > available:
                    raise ValidationError(
                        {
                            "cantidad": [
                                f"El stock {source.id_stock} cambió y ya no tiene saldo suficiente."
                            ]
                        }
                    )
                destination_pallet = detail.id_pallet_destino
                if not destination_pallet and detail.cantidad == source.cantidad_total:
                    destination_pallet = source.id_pallet
                    detail.id_pallet_destino = destination_pallet
                destination = (
                    Stock.objects.select_for_update()
                    .filter(
                        id_producto=source.id_producto,
                        id_lote=source.id_lote,
                        id_ubicacion=detail.id_ubicacion_destino,
                        id_pallet=destination_pallet,
                        estado_stock=source.estado_stock,
                    )
                    .first()
                )
                if destination:
                    destination.cantidad_total += detail.cantidad
                    destination.fecha_actualizacion = now
                    destination.save(
                        update_fields=["cantidad_total", "fecha_actualizacion"]
                    )
                else:
                    destination = Stock.objects.create(
                        id_producto=source.id_producto,
                        id_lote=source.id_lote,
                        id_ubicacion=detail.id_ubicacion_destino,
                        id_pallet=destination_pallet,
                        cantidad_total=detail.cantidad,
                        cantidad_reservada=Decimal("0"),
                        estado_stock=source.estado_stock,
                        fecha_actualizacion=now,
                    )
                source.cantidad_total -= detail.cantidad
                source.fecha_actualizacion = now
                source.save(update_fields=["cantidad_total", "fecha_actualizacion"])
                detail.id_stock_destino = destination.id_stock
                detail.save(
                    update_fields=["id_stock_destino", "id_pallet_destino"]
                )
                if destination_pallet:
                    Pallet.objects.filter(id_pallet=destination_pallet).update(
                        estado="Ocupado", fecha_actualizacion=now
                    )
            movement.estado = "CONFIRMADO"
            movement.id_usuario_confirma = request.user.id
            movement.fecha_confirmacion = now
            movement.fecha_actualizacion = now
            movement.save(
                update_fields=[
                    "estado",
                    "id_usuario_confirma",
                    "fecha_confirmacion",
                    "fecha_actualizacion",
                ]
            )
        return Response(serialize_movements([movement])[0])


class RepackingView(APIView):
    def post(self, request):
        require_application_permission(request.user, "movimientos.reempaque")
        serializer = RepackingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        total = sum(
            (item["cantidad"] for item in data["fracciones"]), Decimal("0")
        )
        now = timezone.now()
        with transaction.atomic():
            source = get_object_or_404(
                Stock.objects.select_for_update(),
                id_stock=data["id_stock_origen"],
            )
            available = source.cantidad_total - source.cantidad_reservada
            if total > available:
                raise ValidationError(
                    {"fracciones": ["La suma supera el stock disponible del pallet."]}
                )
            parent = None
            if source.id_pallet:
                parent = get_object_or_404(Pallet, id_pallet=source.id_pallet)
            else:
                parent = Pallet.objects.create(
                    codigo_barras=f"PLT-STK-{source.id_stock}",
                    tipo="Pallet de origen",
                    capacidad_referencial=source.cantidad_total,
                    id_pallet_padre=None,
                    estado="Ocupado",
                    fecha_registro=now,
                    fecha_actualizacion=now,
                )
                source.id_pallet = parent.id_pallet

            movement = Movimiento.objects.create(
                tipo_movimiento="REEMPAQUE",
                motivo=data["motivo"] or "División o reempaque de pallet",
                estado="CONFIRMADO",
                id_usuario_registro=request.user.id,
                id_usuario_confirma=request.user.id,
                fecha_registro=now,
                fecha_actualizacion=now,
                fecha_confirmacion=now,
            )
            for index, fraction in enumerate(data["fracciones"], start=1):
                code = fraction.get("codigo_pallet", "").strip().upper()
                if not code:
                    code = f"{parent.codigo_barras}-F{index}-{uuid4().hex[:5].upper()}"
                if Pallet.objects.filter(codigo_barras=code).exists():
                    raise ValidationError(
                        {"fracciones": [f"Ya existe el pallet {code}."]}
                    )
                child = Pallet.objects.create(
                    codigo_barras=code,
                    tipo="Fracción",
                    capacidad_referencial=fraction["cantidad"],
                    id_pallet_padre=parent.id_pallet,
                    estado="Ocupado",
                    fecha_registro=now,
                    fecha_actualizacion=now,
                )
                destination = Stock.objects.create(
                    id_producto=source.id_producto,
                    id_lote=source.id_lote,
                    id_ubicacion=source.id_ubicacion,
                    id_pallet=child.id_pallet,
                    cantidad_total=fraction["cantidad"],
                    cantidad_reservada=Decimal("0"),
                    estado_stock=source.estado_stock,
                    fecha_actualizacion=now,
                )
                MovimientoDetalle.objects.create(
                    id_movimiento=movement.id_movimiento,
                    id_stock_origen=source.id_stock,
                    id_ubicacion_origen=source.id_ubicacion,
                    id_ubicacion_destino=source.id_ubicacion,
                    id_pallet_destino=child.id_pallet,
                    id_stock_destino=destination.id_stock,
                    cantidad=fraction["cantidad"],
                )
            source.cantidad_total -= total
            source.fecha_actualizacion = now
            source.save(
                update_fields=["id_pallet", "cantidad_total", "fecha_actualizacion"]
            )
            if source.cantidad_total == 0:
                parent.estado = "Vacío"
                parent.fecha_actualizacion = now
                parent.save(update_fields=["estado", "fecha_actualizacion"])
        return Response(
            serialize_movements([movement])[0], status=status.HTTP_201_CREATED
        )
