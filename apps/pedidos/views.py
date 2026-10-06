from collections import defaultdict
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.inventario.models import Lote, Reserva, Stock
from apps.maestros.models import Cliente, Producto, Ubicacion, Zona
from apps.usuarios.permissions import require_application_permission

from .models import (
    Despacho,
    DespachoDetalle,
    IncidenciaDespacho,
    PedidoDetalle,
    PedidoSalida,
    Picking,
    PickingDetalle,
)
from .serializers import (
    DispatchCloseSerializer,
    DispatchIncidentSerializer,
    OrderCreateSerializer,
    PreparationSerializer,
)
from .services import serialize_orders


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


class OrderListCreateView(APIView):
    def get(self, request):
        require_application_permission(request.user, "pedidos.ver")
        query = PedidoSalida.objects.all().order_by(
            "-fecha_programada", "-fecha_registro"
        )
        client = request.query_params.get("cliente", "").strip()
        if client:
            client_ids = Cliente.objects.filter(
                Q(razon_social__icontains=client) | Q(ruc__icontains=client)
            ).values_list("id_cliente", flat=True)
            query = query.filter(id_cliente__in=client_ids)
        order_status = request.query_params.get("estado", "").strip()
        if order_status:
            query = query.filter(estado=order_status)
        document = request.query_params.get("documento", "").strip()
        if document:
            query = query.filter(codigo_documento__icontains=document)
        responsible = request.query_params.get("responsable", "").strip()
        if responsible:
            from apps.usuarios.models import Usuario

            user_ids = Usuario.objects.filter(
                Q(nombre__icontains=responsible)
                | Q(apellido__icontains=responsible)
                | Q(correo__icontains=responsible)
            ).values_list("id_usuario", flat=True)
            picking_order_ids = Picking.objects.filter(
                id_usuario_asignado__in=user_ids
            ).values_list("id_pedido_salida", flat=True)
            query = query.filter(
                Q(id_usuario_registro__in=user_ids)
                | Q(id_pedido_salida__in=picking_order_ids)
            )
        date_from = _date_param(request, "fecha_desde")
        date_to = _date_param(request, "fecha_hasta")
        if date_from:
            query = query.filter(fecha_programada__gte=date_from)
        if date_to:
            query = query.filter(fecha_programada__lte=date_to)
        if date_from and date_to and date_from > date_to:
            raise ValidationError(
                {"fecha_hasta": ["La fecha final debe ser posterior a la inicial."]}
            )
        return Response(serialize_orders(query[:500]))

    def post(self, request):
        require_application_permission(request.user, "pedidos.crear")
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        lines = data.pop("lineas")
        products = data.pop("product_map")
        data["transporte_placa"] = data["transporte_placa"] or None
        data["transporte_conductor"] = data["transporte_conductor"] or None
        now = timezone.now()
        try:
            with transaction.atomic():
                order = PedidoSalida.objects.create(
                    **data,
                    fecha_despacho=None,
                    estado="Pendiente",
                    id_usuario_registro=request.user.id,
                    fecha_registro=now,
                    fecha_actualizacion=now,
                )
                PedidoDetalle.objects.bulk_create(
                    [
                        PedidoDetalle(
                            id_pedido_salida=order.id_pedido_salida,
                            id_producto=line["id_producto"],
                            id_lote=line["id_lote"],
                            cantidad_solicitada=line["cantidad_solicitada"],
                            cantidad_despachada=Decimal("0"),
                            id_unidad_medida=products[
                                line["id_producto"]
                            ].id_unidad_medida,
                        )
                        for line in lines
                    ]
                )
        except IntegrityError as exc:
            raise ValidationError(
                {"codigo_documento": ["Ya existe un pedido con esta guía de salida."]}
            ) from exc
        return Response(
            serialize_orders([order])[0], status=status.HTTP_201_CREATED
        )


class OrderDetailView(APIView):
    def get(self, request, order_id):
        require_application_permission(request.user, "pedidos.ver")
        order = get_object_or_404(PedidoSalida, id_pedido_salida=order_id)
        return Response(serialize_orders([order])[0])


class OrderDocumentView(APIView):
    def get(self, request, order_id):
        require_application_permission(request.user, "pedidos.imprimir")
        order = get_object_or_404(PedidoSalida, id_pedido_salida=order_id)
        return Response(
            {
                "numero_pedido_salida": f"PS-{order.id_pedido_salida:06d}",
                "pedido": serialize_orders([order])[0],
                "generado_en": timezone.now(),
            }
        )


class OrderStockValidationView(APIView):
    def post(self, request, order_id):
        require_application_permission(request.user, "pedidos.validar_stock")
        now = timezone.now()
        with transaction.atomic():
            order = get_object_or_404(
                PedidoSalida.objects.select_for_update(),
                id_pedido_salida=order_id,
            )
            if order.estado != "Pendiente":
                raise ValidationError(
                    {"estado": ["Solo se puede validar un pedido pendiente."]}
                )
            details = list(
                PedidoDetalle.objects.select_for_update()
                .filter(id_pedido_salida=order_id)
                .order_by("id_pedido_detalle")
            )
            stocks = list(
                Stock.objects.select_for_update()
                .filter(
                    id_producto__in={item.id_producto for item in details},
                    estado_stock="DISP",
                    cantidad_total__gt=0,
                )
                .order_by("id_ubicacion", "id_stock")
            )
            stocks_by_product_lot = defaultdict(list)
            for stock in stocks:
                stocks_by_product_lot[(stock.id_producto, stock.id_lote)].append(
                    stock
                )
            allocations = []
            errors = []
            for detail in details:
                remaining = detail.cantidad_solicitada
                candidates = stocks_by_product_lot[
                    (detail.id_producto, detail.id_lote)
                ]
                available = sum(
                    (
                        stock.cantidad_total - stock.cantidad_reservada
                        for stock in candidates
                    ),
                    Decimal("0"),
                )
                if available < remaining:
                    product = Producto.objects.filter(
                        id_producto=detail.id_producto
                    ).first()
                    errors.append(
                        f"{product.nombre if product else detail.id_producto}: solicitado {detail.cantidad_solicitada}, disponible {available}."
                    )
                    continue
                for stock in candidates:
                    stock_available = stock.cantidad_total - stock.cantidad_reservada
                    if stock_available <= 0:
                        continue
                    quantity = min(stock_available, remaining)
                    allocations.append((detail, stock, quantity))
                    remaining -= quantity
                    if remaining == 0:
                        break
            if errors:
                raise ValidationError({"stock": errors})

            picking = Picking.objects.create(
                id_pedido_salida=order.id_pedido_salida,
                id_usuario_asignado=request.user.id,
                estado="Pendiente",
                fecha_inicio=None,
                fecha_fin=None,
                fecha_registro=now,
                fecha_actualizacion=now,
            )
            for detail, stock, quantity in allocations:
                reservation = Reserva.objects.create(
                    id_stock=stock.id_stock,
                    id_pedido_detalle=detail.id_pedido_detalle,
                    cantidad=quantity,
                    estado="Reservado",
                    fecha_registro=now,
                    fecha_actualizacion=now,
                )
                PickingDetalle.objects.create(
                    id_picking=picking.id_picking,
                    id_reserva=reservation.id_reserva,
                    cantidad_solicitada=quantity,
                    cantidad_confirmada=Decimal("0"),
                )
                stock.cantidad_reservada += quantity
                stock.fecha_actualizacion = now
                stock.save(
                    update_fields=["cantidad_reservada", "fecha_actualizacion"]
                )
            order.estado = "En Preparacion"
            order.fecha_actualizacion = now
            order.save(update_fields=["estado", "fecha_actualizacion"])
        return Response(serialize_orders([order])[0])


class OrderCancelView(APIView):
    def post(self, request, order_id):
        require_application_permission(request.user, "pedidos.cancelar")
        now = timezone.now()
        with transaction.atomic():
            order = get_object_or_404(
                PedidoSalida.objects.select_for_update(),
                id_pedido_salida=order_id,
            )
            if order.estado in {"Despachado", "Cancelado"}:
                raise ValidationError(
                    {"estado": ["El pedido cerrado o cancelado no puede cancelarse."]}
                )
            detail_ids = list(
                PedidoDetalle.objects.filter(
                    id_pedido_salida=order.id_pedido_salida
                ).values_list("id_pedido_detalle", flat=True)
            )
            reservations = list(
                Reserva.objects.select_for_update().filter(
                    id_pedido_detalle__in=detail_ids,
                    estado="Reservado",
                )
            )
            stocks = {
                item.id_stock: item
                for item in Stock.objects.select_for_update().filter(
                    id_stock__in={item.id_stock for item in reservations}
                )
            }
            for reservation in reservations:
                stock = stocks.get(reservation.id_stock)
                if not stock or stock.cantidad_reservada < reservation.cantidad:
                    raise ValidationError(
                        {"stock": ["La reserva no coincide con el inventario actual."]}
                    )
                stock.cantidad_reservada -= reservation.cantidad
                stock.fecha_actualizacion = now
                stock.save(
                    update_fields=["cantidad_reservada", "fecha_actualizacion"]
                )
                reservation.estado = "Liberado"
                reservation.fecha_actualizacion = now
                reservation.save(
                    update_fields=["estado", "fecha_actualizacion"]
                )
            order.estado = "Cancelado"
            order.fecha_actualizacion = now
            order.save(update_fields=["estado", "fecha_actualizacion"])
        return Response(serialize_orders([order])[0])


class OrderPreparationView(APIView):
    def post(self, request, order_id):
        require_application_permission(request.user, "pedidos.preparar")
        serializer = PreparationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        submitted = {
            item["id_picking_detalle"]: item["cantidad_confirmada"]
            for item in serializer.validated_data["lineas"]
        }
        now = timezone.now()
        with transaction.atomic():
            order = get_object_or_404(
                PedidoSalida.objects.select_for_update(),
                id_pedido_salida=order_id,
            )
            if order.estado != "En Preparacion":
                raise ValidationError(
                    {"estado": ["El pedido no se encuentra en preparación."]}
                )
            picking = get_object_or_404(
                Picking.objects.select_for_update(), id_pedido_salida=order_id
            )
            details = list(
                PickingDetalle.objects.select_for_update()
                .filter(id_picking=picking.id_picking)
                .order_by("id_picking_detalle")
            )
            expected_ids = {item.id_picking_detalle for item in details}
            if set(submitted) != expected_ids:
                raise ValidationError(
                    {"lineas": ["Confirma todas las líneas asignadas al picking."]}
                )
            complete = True
            for detail in details:
                quantity = submitted[detail.id_picking_detalle]
                if quantity > detail.cantidad_solicitada:
                    raise ValidationError(
                        {"lineas": ["La cantidad confirmada supera la cantidad reservada."]}
                    )
                detail.cantidad_confirmada = quantity
                detail.save(update_fields=["cantidad_confirmada"])
                if quantity != detail.cantidad_solicitada:
                    complete = False
            picking.id_usuario_asignado = request.user.id
            picking.estado = "Completado" if complete else "En Proceso"
            picking.fecha_inicio = picking.fecha_inicio or now
            picking.fecha_fin = now if complete else None
            picking.fecha_actualizacion = now
            picking.save(
                update_fields=[
                    "id_usuario_asignado",
                    "estado",
                    "fecha_inicio",
                    "fecha_fin",
                    "fecha_actualizacion",
                ]
            )
            if complete:
                order.estado = "Listo"
                order.fecha_actualizacion = now
                order.save(update_fields=["estado", "fecha_actualizacion"])
        return Response(serialize_orders([order])[0])


class OrderDispatchView(APIView):
    def post(self, request, order_id):
        require_application_permission(request.user, "despachos.cerrar")
        serializer = DispatchCloseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        now = timezone.now()
        try:
            with transaction.atomic():
                order = get_object_or_404(
                    PedidoSalida.objects.select_for_update(),
                    id_pedido_salida=order_id,
                )
                if order.estado != "Listo":
                    raise ValidationError(
                        {"estado": ["Solo se puede despachar un pedido listo."]}
                    )
                picking = get_object_or_404(
                    Picking.objects.select_for_update(),
                    id_pedido_salida=order_id,
                    estado="Completado",
                )
                picking_details = list(
                    PickingDetalle.objects.select_for_update().filter(
                        id_picking=picking.id_picking
                    )
                )
                reservations = {
                    item.id_reserva: item
                    for item in Reserva.objects.select_for_update().filter(
                        id_reserva__in=[
                            item.id_reserva for item in picking_details
                        ],
                        estado="Reservado",
                    )
                }
                if len(reservations) != len(picking_details):
                    raise ValidationError(
                        {"stock": ["Una o más reservas ya no están disponibles."]}
                    )
                stocks = {
                    item.id_stock: item
                    for item in Stock.objects.select_for_update().filter(
                        id_stock__in=[
                            item.id_stock for item in reservations.values()
                        ]
                    )
                }
                for picking_detail in picking_details:
                    reservation = reservations[picking_detail.id_reserva]
                    stock = stocks.get(reservation.id_stock)
                    if (
                        not stock
                        or picking_detail.cantidad_confirmada
                        != reservation.cantidad
                        or stock.cantidad_total < reservation.cantidad
                        or stock.cantidad_reservada < reservation.cantidad
                    ):
                        raise ValidationError(
                            {"stock": ["El inventario reservado cambió y no permite cerrar el despacho."]}
                        )

                dispatch = Despacho.objects.create(
                    id_pedido_salida=order.id_pedido_salida,
                    codigo_documento_salida=data["codigo_documento_salida"],
                    fecha_despacho=now,
                    id_usuario_confirma=request.user.id,
                    observaciones=data["observaciones"] or None,
                )
                dispatched_by_detail = defaultdict(Decimal)
                for picking_detail in picking_details:
                    reservation = reservations[picking_detail.id_reserva]
                    stock = stocks[reservation.id_stock]
                    quantity = reservation.cantidad
                    stock.cantidad_total -= quantity
                    stock.cantidad_reservada -= quantity
                    stock.fecha_actualizacion = now
                    stock.save(
                        update_fields=[
                            "cantidad_total",
                            "cantidad_reservada",
                            "fecha_actualizacion",
                        ]
                    )
                    reservation.estado = "Consumido"
                    reservation.fecha_actualizacion = now
                    reservation.save(
                        update_fields=["estado", "fecha_actualizacion"]
                    )
                    DespachoDetalle.objects.create(
                        id_despacho=dispatch.id_despacho,
                        id_picking_detalle=picking_detail.id_picking_detalle,
                        cantidad_despachada=quantity,
                    )
                    dispatched_by_detail[reservation.id_pedido_detalle] += quantity
                order_details = list(
                    PedidoDetalle.objects.select_for_update().filter(
                        id_pedido_salida=order.id_pedido_salida
                    )
                )
                for detail in order_details:
                    detail.cantidad_despachada = dispatched_by_detail[
                        detail.id_pedido_detalle
                    ]
                    detail.save(update_fields=["cantidad_despachada"])
                order.estado = "Despachado"
                order.fecha_despacho = now
                order.fecha_actualizacion = now
                order.save(
                    update_fields=[
                        "estado",
                        "fecha_despacho",
                        "fecha_actualizacion",
                    ]
                )
        except IntegrityError as exc:
            raise ValidationError(
                {"codigo_documento_salida": ["El documento de salida ya está registrado."]}
            ) from exc
        return Response(serialize_orders([order])[0])


class DispatchIncidentView(APIView):
    def post(self, request, order_id):
        require_application_permission(request.user, "despachos.incidencias")
        serializer = DispatchIncidentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        now = timezone.now()
        with transaction.atomic():
            order = get_object_or_404(
                PedidoSalida.objects.select_for_update(),
                id_pedido_salida=order_id,
                estado="Despachado",
            )
            dispatch = get_object_or_404(
                Despacho, id_pedido_salida=order.id_pedido_salida
            )
            order_detail = get_object_or_404(
                PedidoDetalle,
                id_pedido_detalle=data["id_pedido_detalle"],
                id_pedido_salida=order.id_pedido_salida,
            )
            reservation_ids = Reserva.objects.filter(
                id_pedido_detalle=order_detail.id_pedido_detalle
            ).values_list("id_reserva", flat=True)
            picking_detail_ids = PickingDetalle.objects.filter(
                id_reserva__in=reservation_ids
            ).values_list("id_picking_detalle", flat=True)
            dispatch_detail = DespachoDetalle.objects.filter(
                id_despacho=dispatch.id_despacho,
                id_picking_detalle__in=picking_detail_ids,
            ).order_by("id_despacho_detalle").first()
            if not dispatch_detail:
                raise ValidationError(
                    {"id_pedido_detalle": ["El producto no pertenece al despacho."]}
                )
            if data["cantidad"] > order_detail.cantidad_despachada:
                raise ValidationError(
                    {"cantidad": ["La cantidad afectada supera la cantidad despachada."]}
                )
            IncidenciaDespacho.objects.create(
                id_despacho=dispatch.id_despacho,
                id_despacho_detalle=dispatch_detail.id_despacho_detalle,
                tipo=data["tipo"],
                cantidad=data["cantidad"],
                descripcion=data["descripcion"],
                id_usuario_registro=request.user.id,
                fecha_registro=now,
                fecha_actualizacion=now,
            )
        return Response(
            serialize_orders([order])[0], status=status.HTTP_201_CREATED
        )


class DispatchHistoryView(APIView):
    def get(self, request):
        require_application_permission(request.user, "despachos.ver")
        query = PedidoSalida.objects.filter(estado="Despachado")
        client = request.query_params.get("cliente", "").strip()
        if client:
            client_ids = Cliente.objects.filter(
                Q(razon_social__icontains=client) | Q(ruc__icontains=client)
            ).values_list("id_cliente", flat=True)
            query = query.filter(id_cliente__in=client_ids)
        document = request.query_params.get("documento", "").strip()
        if document:
            dispatch_order_ids = Despacho.objects.filter(
                codigo_documento_salida__icontains=document
            ).values_list("id_pedido_salida", flat=True)
            query = query.filter(
                Q(codigo_documento__icontains=document)
                | Q(id_pedido_salida__in=dispatch_order_ids)
            )
        product = request.query_params.get("producto", "").strip()
        if product:
            product_ids = Producto.objects.filter(
                Q(nombre__icontains=product) | Q(sku__icontains=product)
            ).values_list("id_producto", flat=True)
            order_ids = PedidoDetalle.objects.filter(
                id_producto__in=product_ids
            ).values_list("id_pedido_salida", flat=True)
            query = query.filter(id_pedido_salida__in=order_ids)
        responsible = request.query_params.get("responsable", "").strip()
        if responsible:
            from apps.usuarios.models import Usuario

            user_ids = Usuario.objects.filter(
                Q(nombre__icontains=responsible)
                | Q(apellido__icontains=responsible)
                | Q(correo__icontains=responsible)
            ).values_list("id_usuario", flat=True)
            dispatch_ids = Despacho.objects.filter(
                id_usuario_confirma__in=user_ids
            ).values_list("id_pedido_salida", flat=True)
            picking_ids = Picking.objects.filter(
                id_usuario_asignado__in=user_ids
            ).values_list("id_pedido_salida", flat=True)
            query = query.filter(
                Q(id_usuario_registro__in=user_ids)
                | Q(id_pedido_salida__in=dispatch_ids)
                | Q(id_pedido_salida__in=picking_ids)
            )
        date_from = _date_param(request, "fecha_desde")
        date_to = _date_param(request, "fecha_hasta")
        if date_from and date_to and date_from > date_to:
            raise ValidationError(
                {"fecha_hasta": ["La fecha final debe ser posterior a la inicial."]}
            )
        if date_from:
            query = query.filter(fecha_despacho__date__gte=date_from)
        if date_to:
            query = query.filter(fecha_despacho__date__lte=date_to)
        results = serialize_orders(
            query.order_by("-fecha_despacho", "-fecha_registro")[:500]
        )
        timing_fields = {
            "preparacion_minutos": [],
            "despacho_minutos": [],
            "total_minutos": [],
        }
        for item in results:
            for field in timing_fields:
                value = item["tiempos"][field]
                if value is not None:
                    timing_fields[field].append(value)
        return Response(
            {
                "resumen": {
                    "despachos": len(results),
                    "unidades": sum(
                        (item["cantidad_despachada"] for item in results),
                        Decimal("0"),
                    ),
                    "preparacion_promedio_minutos": round(
                        sum(timing_fields["preparacion_minutos"])
                        / len(timing_fields["preparacion_minutos"]),
                        2,
                    )
                    if timing_fields["preparacion_minutos"]
                    else None,
                    "despacho_promedio_minutos": round(
                        sum(timing_fields["despacho_minutos"])
                        / len(timing_fields["despacho_minutos"]),
                        2,
                    )
                    if timing_fields["despacho_minutos"]
                    else None,
                    "total_promedio_minutos": round(
                        sum(timing_fields["total_minutos"])
                        / len(timing_fields["total_minutos"]),
                        2,
                    )
                    if timing_fields["total_minutos"]
                    else None,
                },
                "resultados": results,
            }
        )


class OrderOptionsView(APIView):
    def get(self, request):
        require_application_permission(request.user, "pedidos.ver")
        clients = list(Cliente.objects.filter(estado=True).order_by("razon_social"))
        products = list(Producto.objects.filter(estado=True).order_by("nombre"))
        lots = list(
            Lote.objects.filter(
                id_producto__in=[item.id_producto for item in products]
            ).order_by("fecha_vencimiento", "codigo")
        )
        stocks = list(
            Stock.objects.filter(
                id_producto__in=[item.id_producto for item in products],
                estado_stock="DISP",
                cantidad_total__gt=0,
            )
        )
        locations = {
            item.id_ubicacion: item
            for item in Ubicacion.objects.filter(
                id_ubicacion__in={item.id_ubicacion for item in stocks}
            )
        }
        zones = {
            item.id_zona: item
            for item in Zona.objects.filter(
                id_zona__in={item.id_zona for item in locations.values()}
            )
        }
        available_by_lot = defaultdict(Decimal)
        for item in stocks:
            available_by_lot[item.id_lote] += (
                item.cantidad_total - item.cantidad_reservada
            )
        fefo_by_product = {}
        for item in lots:
            if (
                available_by_lot[item.id_lote] > 0
                and (
                    item.fecha_vencimiento is None
                    or item.fecha_vencimiento >= timezone.localdate()
                )
                and item.id_producto not in fefo_by_product
            ):
                fefo_by_product[item.id_producto] = item.id_lote
        return Response(
            {
                "clientes": [
                    {
                        "id_cliente": item.id_cliente,
                        "razon_social": item.razon_social,
                        "ruc": item.ruc,
                    }
                    for item in clients
                ],
                "productos": [
                    {
                        "id_producto": item.id_producto,
                        "id_cliente": item.id_cliente,
                        "sku": item.sku,
                        "nombre": item.nombre,
                        "controla_lote": item.controla_lote,
                    }
                    for item in products
                ],
                "lotes": [
                    {
                        "id_lote": item.id_lote,
                        "id_producto": item.id_producto,
                        "codigo": item.codigo,
                        "fecha_vencimiento": item.fecha_vencimiento,
                        "cantidad_disponible": available_by_lot[item.id_lote],
                        "sugerido_fefo": fefo_by_product.get(item.id_producto)
                        == item.id_lote,
                    }
                    for item in lots
                ],
                "stocks": [
                    {
                        "id_stock": item.id_stock,
                        "id_producto": item.id_producto,
                        "id_lote": item.id_lote,
                        "ubicacion": locations[item.id_ubicacion].codigo
                        if item.id_ubicacion in locations
                        else None,
                        "zona": zones[locations[item.id_ubicacion].id_zona].nombre
                        if item.id_ubicacion in locations
                        and locations[item.id_ubicacion].id_zona in zones
                        else None,
                        "cantidad_disponible": item.cantidad_total
                        - item.cantidad_reservada,
                    }
                    for item in stocks
                ],
                "estados": [
                    "Pendiente",
                    "En Preparacion",
                    "Listo",
                    "Despachado",
                    "Cancelado",
                ],
            }
        )
