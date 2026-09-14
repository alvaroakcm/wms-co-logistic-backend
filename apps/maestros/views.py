from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.inventario.models import Stock
from apps.usuarios.permissions import require_application_permission

from .importers import import_master_data
from .models import (
    Almacen,
    CategoriaProducto,
    Cliente,
    Producto,
    Ubicacion,
    UnidadMedida,
    Zona,
)
from .serializers import (
    AlmacenWriteSerializer,
    ClienteWriteSerializer,
    ProductoWriteSerializer,
    ProductoConversionCalculationSerializer,
    UbicacionWriteSerializer,
    ZonaWriteSerializer,
)
from .services import (
    calculate_product_boxes,
    serialize_client,
    serialize_locations,
    serialize_products,
    sync_product_conversion,
    serialize_warehouse,
    serialize_zone,
)


def _parse_status(value):
    if value in (None, ""):
        return None
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "activo"}:
        return True
    if normalized in {"false", "0", "inactivo"}:
        return False
    raise ValidationError({"estado": ["El estado debe ser activo o inactivo."]})


class ClienteListCreateView(APIView):
    def get(self, request):
        require_application_permission(request.user, "clientes.ver")
        query = Cliente.objects.all().order_by("razon_social")
        search = request.query_params.get("search", "").strip()
        if search:
            query = query.filter(
                Q(razon_social__icontains=search)
                | Q(ruc__icontains=search)
                | Q(contacto_nombre__icontains=search)
            )
        active = _parse_status(request.query_params.get("estado"))
        if active is not None:
            query = query.filter(estado=active)
        return Response([serialize_client(client) for client in query[:500]])

    def post(self, request):
        require_application_permission(request.user, "clientes.crear")
        serializer = ClienteWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        now = timezone.now()
        try:
            with transaction.atomic():
                client = Cliente.objects.create(
                    razon_social=data["razon_social"],
                    ruc=data["ruc"],
                    contacto_nombre=data["contacto_nombre"] or None,
                    contacto_telefono=data["contacto_telefono"] or None,
                    estado=data["estado"],
                    fecha_registro=now,
                    fecha_actualizacion=now,
                )
        except IntegrityError as exc:
            raise ValidationError(
                {"ruc": ["Ya existe un cliente con este RUC."]}
            ) from exc
        return Response(serialize_client(client), status=status.HTTP_201_CREATED)


class ClienteDetailView(APIView):
    def patch(self, request, client_id):
        require_application_permission(request.user, "clientes.editar")
        client = get_object_or_404(Cliente, id_cliente=client_id)
        serializer = ClienteWriteSerializer(
            data=request.data, context={"client_id": client.id_cliente}
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        client.razon_social = data["razon_social"]
        client.ruc = data["ruc"]
        client.contacto_nombre = data["contacto_nombre"] or None
        client.contacto_telefono = data["contacto_telefono"] or None
        client.estado = data["estado"]
        client.fecha_actualizacion = timezone.now()
        try:
            with transaction.atomic():
                client.save(
                    update_fields=[
                        "razon_social",
                        "ruc",
                        "contacto_nombre",
                        "contacto_telefono",
                        "estado",
                        "fecha_actualizacion",
                    ]
                )
        except IntegrityError as exc:
            raise ValidationError(
                {"ruc": ["Ya existe un cliente con este RUC."]}
            ) from exc
        return Response(serialize_client(client))


class ProductoListCreateView(APIView):
    def get(self, request):
        require_application_permission(request.user, "productos.ver")
        query = Producto.objects.all().order_by("nombre", "sku")
        code = request.query_params.get("codigo", "").strip()
        name = request.query_params.get("nombre", "").strip()
        client = request.query_params.get("cliente", "").strip()
        if code:
            query = query.filter(
                Q(sku__icontains=code) | Q(codigo_ean__icontains=code)
            )
        if name:
            query = query.filter(nombre__icontains=name)
        if client:
            client_ids = Cliente.objects.filter(
                Q(razon_social__icontains=client) | Q(ruc__icontains=client)
            ).values_list("id_cliente", flat=True)
            query = query.filter(id_cliente__in=client_ids)
        active = _parse_status(request.query_params.get("estado"))
        if active is not None:
            query = query.filter(estado=active)
        return Response(serialize_products(query[:500]))

    def post(self, request):
        require_application_permission(request.user, "productos.crear")
        serializer = ProductoWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        factor_conversion = data.pop("factor_conversion", None)
        now = timezone.now()
        try:
            with transaction.atomic():
                product = Producto.objects.create(
                    **data,
                    fecha_registro=now,
                    fecha_actualizacion=now,
                )
                sync_product_conversion(product, factor_conversion)
        except IntegrityError as exc:
            raise ValidationError(
                {"codigo": ["El SKU o el código EAN ya está registrado."]}
            ) from exc
        return Response(
            serialize_products([product])[0], status=status.HTTP_201_CREATED
        )


class ProductoDetailView(APIView):
    def patch(self, request, product_id):
        require_application_permission(request.user, "productos.editar")
        product = get_object_or_404(Producto, id_producto=product_id)
        serializer = ProductoWriteSerializer(
            data=request.data,
            context={
                "product_id": product.id_producto,
                "current_client_id": product.id_cliente,
                "current_category_id": product.id_categoria,
                "current_unit_id": product.id_unidad_medida,
            },
        )
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        factor_conversion = data.pop("factor_conversion", None)
        for field, value in data.items():
            setattr(product, field, value)
        product.fecha_actualizacion = timezone.now()
        try:
            with transaction.atomic():
                product.save(
                    update_fields=[
                        *data.keys(),
                        "fecha_actualizacion",
                    ]
                )
                sync_product_conversion(product, factor_conversion)
        except IntegrityError as exc:
            raise ValidationError(
                {"codigo": ["El SKU o el código EAN ya está registrado."]}
            ) from exc
        return Response(serialize_products([product])[0])


class ProductoConversionCalculationView(APIView):
    def post(self, request, product_id):
        require_application_permission(request.user, "productos.ver")
        product = get_object_or_404(Producto, id_producto=product_id)
        serializer = ProductoConversionCalculationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pallet_quantity = serializer.validated_data["cantidad_pallets"]
        boxes = calculate_product_boxes(product, pallet_quantity)
        if boxes is None:
            raise ValidationError(
                {
                    "producto": [
                        "Este producto se gestiona por unidad y no utiliza conversión desde pallets."
                    ]
                }
            )
        product_data = serialize_products([product])[0]
        return Response(
            {
                "id_producto": product.id_producto,
                "sku": product.sku,
                "cantidad_pallets": str(pallet_quantity),
                "factor_conversion": product_data["factor_conversion"],
                "cantidad_cajas": str(boxes),
            }
        )


class ProductOptionsView(APIView):
    def get(self, request):
        require_application_permission(request.user, "productos.ver")
        return Response(
            {
                "clientes": list(
                    Cliente.objects.order_by("razon_social").values(
                        "id_cliente", "razon_social", "ruc", "estado"
                    )
                ),
                "categorias": list(
                    CategoriaProducto.objects.order_by("nombre").values(
                        "id_categoria", "nombre", "estado"
                    )
                ),
                "unidades": list(
                    UnidadMedida.objects.order_by("nombre").values(
                        "id_unidad_medida", "codigo", "nombre", "estado"
                    )
                ),
            }
        )


class AlmacenListCreateView(APIView):
    def get(self, request):
        require_application_permission(request.user, "almacenes.ver")
        query = Almacen.objects.all().order_by("nombre")
        search = request.query_params.get("search", "").strip()
        if search:
            query = query.filter(
                Q(codigo__icontains=search)
                | Q(nombre__icontains=search)
                | Q(referencia__icontains=search)
            )
        active = _parse_status(request.query_params.get("estado"))
        if active is not None:
            query = query.filter(estado=active)
        return Response([serialize_warehouse(item) for item in query[:500]])

    def post(self, request):
        require_application_permission(request.user, "almacenes.crear")
        serializer = AlmacenWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        now = timezone.now()
        try:
            with transaction.atomic():
                warehouse = Almacen.objects.create(
                    **{**data, "referencia": data["referencia"] or None},
                    fecha_registro=now,
                    fecha_actualizacion=now,
                )
        except IntegrityError as exc:
            raise ValidationError(
                {"codigo": ["Ya existe un almacén con este código."]}
            ) from exc
        return Response(
            serialize_warehouse(warehouse), status=status.HTTP_201_CREATED
        )


class ZonaListCreateView(APIView):
    def get(self, request):
        require_application_permission(request.user, "ubicaciones.ver")
        query = Zona.objects.all().order_by("id_almacen", "codigo")
        warehouse_id = request.query_params.get("almacen")
        if warehouse_id:
            query = query.filter(id_almacen=warehouse_id)
        active = _parse_status(request.query_params.get("estado"))
        if active is not None:
            query = query.filter(estado=active)
        warehouses = {
            item.id_almacen: item
            for item in Almacen.objects.filter(
                id_almacen__in=query.values_list("id_almacen", flat=True)
            )
        }
        return Response([serialize_zone(item, warehouses) for item in query[:500]])

    def post(self, request):
        require_application_permission(request.user, "ubicaciones.crear")
        serializer = ZonaWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        now = timezone.now()
        try:
            with transaction.atomic():
                zone = Zona.objects.create(
                    **serializer.validated_data,
                    fecha_registro=now,
                    fecha_actualizacion=now,
                )
        except IntegrityError as exc:
            raise ValidationError(
                {"codigo": ["Ya existe esta zona dentro del almacén."]}
            ) from exc
        warehouse = Almacen.objects.get(id_almacen=zone.id_almacen)
        return Response(
            serialize_zone(zone, {warehouse.id_almacen: warehouse}),
            status=status.HTTP_201_CREATED,
        )


class UbicacionListCreateView(APIView):
    def get(self, request):
        require_application_permission(request.user, "ubicaciones.ver")
        query = Ubicacion.objects.all().order_by("codigo")
        warehouse_id = request.query_params.get("almacen", "").strip()
        zone_term = request.query_params.get("zona", "").strip()
        rack = request.query_params.get("rack", "").strip()
        if warehouse_id:
            zone_ids = Zona.objects.filter(id_almacen=warehouse_id).values_list(
                "id_zona", flat=True
            )
            query = query.filter(id_zona__in=zone_ids)
        if zone_term:
            zone_ids = Zona.objects.filter(
                Q(codigo__icontains=zone_term) | Q(nombre__icontains=zone_term)
            ).values_list("id_zona", flat=True)
            query = query.filter(id_zona__in=zone_ids)
        if rack:
            query = query.filter(rack__icontains=rack)

        location_status = request.query_params.get("estado", "").strip().lower()
        occupied_ids = Stock.objects.filter(cantidad_total__gt=0).values_list(
            "id_ubicacion", flat=True
        )
        if location_status == "disponible":
            query = query.filter(estado=True).exclude(id_ubicacion__in=occupied_ids)
        elif location_status == "ocupada":
            query = query.filter(estado=True, id_ubicacion__in=occupied_ids)
        elif location_status == "inactiva":
            query = query.filter(estado=False)
        elif location_status:
            active = _parse_status(location_status)
            query = query.filter(estado=active)
        return Response(serialize_locations(query[:500]))

    def post(self, request):
        require_application_permission(request.user, "ubicaciones.crear")
        serializer = UbicacionWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        now = timezone.now()
        try:
            with transaction.atomic():
                location = Ubicacion.objects.create(
                    **serializer.validated_data,
                    fecha_registro=now,
                    fecha_actualizacion=now,
                )
        except IntegrityError as exc:
            raise ValidationError(
                {"codigo": ["Ya existe una ubicación con este código."]}
            ) from exc
        return Response(
            serialize_locations([location])[0], status=status.HTTP_201_CREATED
        )


class UbicacionDetailView(APIView):
    def patch(self, request, location_id):
        require_application_permission(request.user, "ubicaciones.editar")
        location = get_object_or_404(Ubicacion, id_ubicacion=location_id)
        serializer = UbicacionWriteSerializer(
            data=request.data,
            context={
                "location_id": location.id_ubicacion,
                "current_zone_id": location.id_zona,
            },
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if location.estado and not data["estado"] and Stock.objects.filter(
            id_ubicacion=location.id_ubicacion, cantidad_total__gt=0
        ).exists():
            raise ValidationError(
                {
                    "estado": [
                        "No se puede desactivar una ubicación con stock activo."
                    ]
                }
            )
        for field, value in data.items():
            setattr(location, field, value)
        location.fecha_actualizacion = timezone.now()
        try:
            with transaction.atomic():
                location.save(
                    update_fields=[*data.keys(), "fecha_actualizacion"]
                )
        except IntegrityError as exc:
            raise ValidationError(
                {"codigo": ["Ya existe una ubicación con este código."]}
            ) from exc
        return Response(serialize_locations([location])[0])


class LocationOptionsView(APIView):
    def get(self, request):
        require_application_permission(request.user, "ubicaciones.ver")
        return Response(
            {
                "almacenes": list(
                    Almacen.objects.order_by("nombre").values(
                        "id_almacen", "codigo", "nombre", "estado"
                    )
                ),
                "zonas": list(
                    Zona.objects.order_by("id_almacen", "codigo").values(
                        "id_zona",
                        "id_almacen",
                        "codigo",
                        "nombre",
                        "tipo",
                        "estado",
                    )
                ),
            }
        )


class MasterDataImportView(APIView):
    def post(self, request):
        require_application_permission(request.user, "importaciones.ejecutar")
        report = import_master_data(
            request.FILES.get("archivo"), request.data.get("tipo", "")
        )
        return Response(report)
