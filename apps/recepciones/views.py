from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.inventario.models import AsignacionUbicacion, Lote, Stock
from apps.maestros.models import Cliente, Producto, ProductoConversion, Ubicacion
from apps.usuarios.permissions import require_application_permission

from .models import (
    Discrepancia,
    IncidenciaRecepcion,
    PedidoIngreso,
    PedidoIngresoDetalle,
    PedidoIngresoLote,
)
from .serializers import (
    IncidentCreateSerializer,
    LocationAssignmentSerializer,
    ReceptionCreateSerializer,
    ReceptionLotsSerializer,
    ReceptionValidationSerializer,
)
from .services import (
    available_locations,
    serialize_receipt_detail,
    serialize_receipts,
)


FINAL_STATES = {"Recibido", "Con Discrepancia", "Cancelado"}


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


class ReceptionListCreateView(APIView):
    def get(self, request):
        require_application_permission(request.user, "recepciones.ver")
        query = PedidoIngreso.objects.all().order_by("-fecha_registro")

        client = request.query_params.get("cliente", "").strip()
        if client:
            client_ids = Cliente.objects.filter(
                Q(razon_social__icontains=client) | Q(ruc__icontains=client)
            ).values_list("id_cliente", flat=True)
            query = query.filter(id_cliente__in=client_ids)

        product = request.query_params.get("producto", "").strip()
        if product:
            product_ids = Producto.objects.filter(
                Q(sku__icontains=product)
                | Q(codigo_ean__icontains=product)
                | Q(nombre__icontains=product)
            ).values_list("id_producto", flat=True)
            receipt_ids = PedidoIngresoDetalle.objects.filter(
                id_producto__in=product_ids
            ).values_list("id_pedido_ingreso", flat=True)
            query = query.filter(id_pedido_ingreso__in=receipt_ids)

        document = request.query_params.get("documento", "").strip()
        if document:
            query = query.filter(codigo_documento__icontains=document)
        receipt_status = request.query_params.get("estado", "").strip()
        if receipt_status:
            query = query.filter(estado__iexact=receipt_status)
        responsible = request.query_params.get("responsable", "").strip()
        if responsible:
            from apps.usuarios.models import Usuario

            user_ids = Usuario.objects.filter(
                Q(nombre__icontains=responsible)
                | Q(apellido__icontains=responsible)
                | Q(correo__icontains=responsible)
            ).values_list("id_usuario", flat=True)
            query = query.filter(id_usuario_registro__in=user_ids)

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
        return Response(serialize_receipts(query[:300]))

    def post(self, request):
        require_application_permission(request.user, "recepciones.crear")
        serializer = ReceptionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        lines = data.pop("lineas")
        products = data.pop("product_map")
        conversions = data.pop("conversion_map")
        data["transporte_placa"] = data["transporte_placa"] or None
        data["transporte_conductor"] = data["transporte_conductor"] or None
        data["transporte_brevete"] = data["transporte_brevete"] or None
        now = timezone.now()
        try:
            with transaction.atomic():
                receipt = PedidoIngreso.objects.create(
                    **data,
                    fecha_recepcion=None,
                    estado="Pendiente",
                    id_usuario_registro=request.user.id,
                    fecha_registro=now,
                    fecha_actualizacion=now,
                )
                PedidoIngresoDetalle.objects.bulk_create(
                    [
                        PedidoIngresoDetalle(
                            id_pedido_ingreso=receipt.id_pedido_ingreso,
                            id_producto=line["id_producto"],
                            codigo_producto=products[line["id_producto"]].sku,
                            descripcion_producto=products[line["id_producto"]].nombre,
                            cantidad_pallets=line["cantidad_pallets"],
                            factor_conversion=(
                                conversions[line["id_producto"]].factor_conversion
                                if line["id_producto"] in conversions
                                else None
                            ),
                            cantidad_esperada=line["cantidad_esperada"],
                            cantidad_recibida=Decimal("0"),
                            cantidad_rechazada=Decimal("0"),
                            id_unidad_medida=products[
                                line["id_producto"]
                            ].id_unidad_medida,
                        )
                        for line in lines
                    ]
                )
        except IntegrityError as exc:
            raise ValidationError(
                {
                    "codigo_documento": [
                        "Ya existe una recepción con esta guía de remisión."
                    ]
                }
            ) from exc
        return Response(
            serialize_receipt_detail(receipt), status=status.HTTP_201_CREATED
        )


class ReceptionDetailView(APIView):
    def get(self, request, receipt_id):
        require_application_permission(request.user, "recepciones.ver")
        receipt = get_object_or_404(
            PedidoIngreso, id_pedido_ingreso=receipt_id
        )
        return Response(serialize_receipt_detail(receipt))


class ReceptionDocumentView(APIView):
    def get(self, request, receipt_id):
        require_application_permission(request.user, "recepciones.imprimir")
        receipt = get_object_or_404(
            PedidoIngreso, id_pedido_ingreso=receipt_id
        )
        document = serialize_receipt_detail(receipt)
        document["numero_pedido_ingreso"] = f"PI-{receipt_id:06d}"
        return Response(document)


class ReceptionValidateView(APIView):
    def post(self, request, receipt_id):
        require_application_permission(request.user, "recepciones.validar")
        serializer = ReceptionValidationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        submitted = {
            line["id_pedido_ingreso_detalle"]: line
            for line in serializer.validated_data["lineas"]
        }
        with transaction.atomic():
            receipt = get_object_or_404(
                PedidoIngreso.objects.select_for_update(),
                id_pedido_ingreso=receipt_id,
            )
            if receipt.estado in FINAL_STATES:
                raise ValidationError(
                    {"estado": ["Esta recepción ya fue cerrada o cancelada."]}
                )
            details = list(
                PedidoIngresoDetalle.objects.select_for_update()
                .filter(id_pedido_ingreso=receipt_id)
                .order_by("id_pedido_ingreso_detalle")
            )
            expected_ids = {
                detail.id_pedido_ingreso_detalle for detail in details
            }
            if set(submitted) != expected_ids:
                raise ValidationError(
                    {
                        "lineas": [
                            "Debes validar todas las líneas declaradas en la guía."
                        ]
                    }
                )

            Discrepancia.objects.filter(id_pedido_ingreso=receipt_id).delete()
            has_discrepancy = False
            now = timezone.now()
            for detail in details:
                values = submitted[detail.id_pedido_ingreso_detalle]
                received = values["cantidad_recibida"]
                rejected = values["cantidad_rechazada"]
                detail.cantidad_recibida = received
                detail.cantidad_rechazada = rejected
                detail.save(
                    update_fields=["cantidad_recibida", "cantidad_rechazada"]
                )

                difference = received - detail.cantidad_esperada
                if difference:
                    has_discrepancy = True
                    Discrepancia.objects.create(
                        id_pedido_ingreso=receipt_id,
                        id_pedido_ingreso_detalle=detail.id_pedido_ingreso_detalle,
                        tipo="SOBRANTE" if difference > 0 else "FALTANTE",
                        cantidad=abs(difference),
                        descripcion=values["observacion"]
                        or "Diferencia entre la guía y el conteo físico.",
                        fecha_registro=now,
                        fecha_actualizacion=now,
                    )
                if rejected:
                    has_discrepancy = True
                    Discrepancia.objects.create(
                        id_pedido_ingreso=receipt_id,
                        id_pedido_ingreso_detalle=detail.id_pedido_ingreso_detalle,
                        tipo="RECHAZADO",
                        cantidad=rejected,
                        descripcion=values["observacion"]
                        or "Mercancía rechazada durante la recepción.",
                        fecha_registro=now,
                        fecha_actualizacion=now,
                    )

            receipt.estado = (
                "Con Discrepancia" if has_discrepancy else "Recibido"
            )
            receipt.fecha_recepcion = now
            receipt.fecha_actualizacion = now
            receipt.save(
                update_fields=[
                    "estado",
                    "fecha_recepcion",
                    "fecha_actualizacion",
                ]
            )
        return Response(serialize_receipt_detail(receipt))


class ReceptionLocationAssignmentView(APIView):
    def post(self, request, receipt_id):
        require_application_permission(
            request.user, "recepciones.asignar_ubicacion"
        )
        serializer = LocationAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        with transaction.atomic():
            receipt = get_object_or_404(
                PedidoIngreso.objects.select_for_update(),
                id_pedido_ingreso=receipt_id,
            )
            if receipt.estado not in {"Recibido", "Con Discrepancia"}:
                raise ValidationError(
                    {
                        "estado": [
                            "Valida la recepción antes de asignar una ubicación."
                        ]
                    }
                )
            detail = get_object_or_404(
                PedidoIngresoDetalle.objects.select_for_update(),
                id_pedido_ingreso_detalle=data[
                    "id_pedido_ingreso_detalle"
                ],
                id_pedido_ingreso=receipt_id,
            )
            product = get_object_or_404(
                Producto, id_producto=detail.id_producto
            )
            stock_ids = AsignacionUbicacion.objects.filter(
                id_pedido_ingreso=receipt_id
            ).values_list("id_stock", flat=True)
            declared_lot = None
            if product.controla_lote:
                if data["id_pedido_ingreso_lote"] is None:
                    raise ValidationError(
                        {"id_pedido_ingreso_lote": ["Selecciona el lote a ubicar."]}
                    )
                declared_lot = get_object_or_404(
                    PedidoIngresoLote,
                    id_pedido_ingreso_lote=data["id_pedido_ingreso_lote"],
                    id_pedido_ingreso_detalle=(
                        detail.id_pedido_ingreso_detalle
                    ),
                )
                assignable = declared_lot.cantidad
                assigned_stock_ids = Stock.objects.filter(
                    id_stock__in=stock_ids,
                    id_lote=declared_lot.id_lote,
                ).values_list("id_stock", flat=True)
            else:
                if data["id_pedido_ingreso_lote"] is not None:
                    raise ValidationError(
                        {
                            "id_pedido_ingreso_lote": [
                                "Este producto no requiere control por lote."
                            ]
                        }
                    )
                assignable = (
                    detail.cantidad_recibida - detail.cantidad_rechazada
                )
                assigned_stock_ids = Stock.objects.filter(
                    id_stock__in=stock_ids,
                    id_producto=detail.id_producto,
                    id_lote__isnull=True,
                ).values_list("id_stock", flat=True)
            assigned = (
                AsignacionUbicacion.objects.filter(
                    id_pedido_ingreso=receipt_id,
                    id_stock__in=assigned_stock_ids,
                ).aggregate(total=Sum("cantidad"))["total"]
                or Decimal("0")
            )
            if data["cantidad"] > assignable - assigned:
                raise ValidationError(
                    {
                        "cantidad": [
                            "La cantidad excede la mercancía recibida disponible para ubicar."
                        ]
                    }
                )
            location = get_object_or_404(
                Ubicacion.objects.select_for_update(),
                id_ubicacion=data["id_ubicacion"],
                estado=True,
            )
            if Stock.objects.select_for_update().filter(
                id_ubicacion=location.id_ubicacion,
                cantidad_total__gt=0,
            ).exists():
                raise ValidationError(
                    {"id_ubicacion": ["La ubicación seleccionada ya está ocupada."]}
                )
            now = timezone.now()
            stock = Stock.objects.create(
                id_producto=detail.id_producto,
                id_lote=(declared_lot.id_lote if declared_lot else None),
                id_ubicacion=location.id_ubicacion,
                id_pallet=None,
                cantidad_total=data["cantidad"],
                cantidad_reservada=Decimal("0"),
                estado_stock="DISP",
                fecha_actualizacion=now,
            )
            AsignacionUbicacion.objects.create(
                id_stock=stock.id_stock,
                id_pedido_ingreso=receipt_id,
                id_ubicacion=location.id_ubicacion,
                id_pallet=None,
                cantidad=data["cantidad"],
                id_usuario_responsable=request.user.id,
                fecha_asignacion=now,
            )
            receipt.fecha_actualizacion = now
            receipt.save(update_fields=["fecha_actualizacion"])
        return Response(
            serialize_receipt_detail(receipt), status=status.HTTP_201_CREATED
        )


class ReceptionLotsView(APIView):
    def post(self, request, receipt_id):
        require_application_permission(request.user, "recepciones.lotes")
        serializer = ReceptionLotsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        with transaction.atomic():
            receipt = get_object_or_404(
                PedidoIngreso.objects.select_for_update(),
                id_pedido_ingreso=receipt_id,
            )
            if receipt.estado not in {"Recibido", "Con Discrepancia"}:
                raise ValidationError(
                    {"estado": ["Valida la recepción antes de registrar lotes."]}
                )
            detail = get_object_or_404(
                PedidoIngresoDetalle.objects.select_for_update(),
                id_pedido_ingreso_detalle=data[
                    "id_pedido_ingreso_detalle"
                ],
                id_pedido_ingreso=receipt_id,
            )
            product = get_object_or_404(
                Producto, id_producto=detail.id_producto
            )
            if not product.controla_lote:
                raise ValidationError(
                    {"lotes": ["Este producto no está configurado por lote."]}
                )
            if AsignacionUbicacion.objects.filter(
                id_pedido_ingreso=receipt_id,
                id_stock__in=Stock.objects.filter(
                    id_producto=detail.id_producto
                ).values_list("id_stock", flat=True),
            ).exists():
                raise ValidationError(
                    {
                        "lotes": [
                            "No puedes cambiar lotes que ya tienen ubicación asignada."
                        ]
                    }
                )
            assignable = detail.cantidad_recibida - detail.cantidad_rechazada
            declared_total = sum(
                (item["cantidad"] for item in data["lotes"]), Decimal("0")
            )
            if declared_total != assignable:
                raise ValidationError(
                    {
                        "lotes": [
                            f"La suma de lotes debe ser igual a {assignable}."
                        ]
                    }
                )

            PedidoIngresoLote.objects.filter(
                id_pedido_ingreso_detalle=detail.id_pedido_ingreso_detalle
            ).delete()
            now = timezone.now()
            for values in data["lotes"]:
                lot = Lote.objects.filter(
                    id_producto=product.id_producto,
                    codigo=values["codigo"],
                ).first()
                if lot:
                    if (
                        lot.fecha_vencimiento != values["fecha_vencimiento"]
                        or (
                            lot.fecha_fabricacion is not None
                            and values.get("fecha_fabricacion") is not None
                            and lot.fecha_fabricacion
                            != values["fecha_fabricacion"]
                        )
                    ):
                        raise ValidationError(
                            {
                                "lotes": [
                                    f"El lote {values['codigo']} ya existe con fechas diferentes."
                                ]
                            }
                        )
                    if (
                        lot.fecha_fabricacion is None
                        and values.get("fecha_fabricacion") is not None
                    ):
                        lot.fecha_fabricacion = values["fecha_fabricacion"]
                        lot.fecha_actualizacion = now
                        lot.save(
                            update_fields=[
                                "fecha_fabricacion",
                                "fecha_actualizacion",
                            ]
                        )
                else:
                    lot = Lote.objects.create(
                        id_producto=product.id_producto,
                        codigo=values["codigo"],
                        fecha_fabricacion=values.get("fecha_fabricacion"),
                        fecha_vencimiento=values["fecha_vencimiento"],
                        fecha_registro=now,
                        fecha_actualizacion=now,
                    )
                PedidoIngresoLote.objects.create(
                    id_pedido_ingreso_detalle=(
                        detail.id_pedido_ingreso_detalle
                    ),
                    id_lote=lot.id_lote,
                    cantidad=values["cantidad"],
                    fecha_registro=now,
                )
            receipt.fecha_actualizacion = now
            receipt.save(update_fields=["fecha_actualizacion"])
        return Response(serialize_receipt_detail(receipt))


class ReceptionIncidentCreateView(APIView):
    def post(self, request, receipt_id):
        require_application_permission(request.user, "recepciones.incidencias")
        serializer = IncidentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        receipt = get_object_or_404(
            PedidoIngreso, id_pedido_ingreso=receipt_id
        )
        detail = get_object_or_404(
            PedidoIngresoDetalle,
            id_pedido_ingreso_detalle=data["id_pedido_ingreso_detalle"],
            id_pedido_ingreso=receipt_id,
        )
        incident = IncidenciaRecepcion.objects.create(
            id_pedido_ingreso=receipt_id,
            id_pedido_ingreso_detalle=detail.id_pedido_ingreso_detalle,
            tipo=data["tipo"],
            descripcion=data["descripcion"],
            cantidad_afectada=data["cantidad_afectada"],
            id_usuario_responsable=request.user.id,
            fecha_registro=timezone.now(),
        )
        receipt.fecha_actualizacion = timezone.now()
        receipt.save(update_fields=["fecha_actualizacion"])
        return Response(
            {
                "id_incidencia": incident.id_incidencia,
                "recepcion": serialize_receipt_detail(receipt),
            },
            status=status.HTTP_201_CREATED,
        )


class ReceptionOptionsView(APIView):
    def get(self, request):
        require_application_permission(request.user, "recepciones.ver")
        products = list(Producto.objects.filter(estado=True).order_by("nombre"))
        conversions = {
            item.id_producto: item.factor_conversion
            for item in ProductoConversion.objects.filter(
                id_producto__in={product.id_producto for product in products}
            )
        }
        return Response(
            {
                "clientes": list(
                    Cliente.objects.filter(estado=True)
                    .order_by("razon_social")
                    .values("id_cliente", "razon_social", "ruc")
                ),
                "productos": [
                    {
                        "id_producto": product.id_producto,
                        "id_cliente": product.id_cliente,
                        "id_unidad_medida": product.id_unidad_medida,
                        "sku": product.sku,
                        "nombre": product.nombre,
                        "controla_lote": product.controla_lote,
                        "factor_conversion": conversions.get(
                            product.id_producto
                        ),
                    }
                    for product in products
                ],
                "ubicaciones": available_locations(),
                "estados": [
                    "Pendiente",
                    "En Proceso",
                    "Recibido",
                    "Con Discrepancia",
                    "Cancelado",
                ],
            }
        )
