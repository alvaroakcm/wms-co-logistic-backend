import csv
import io

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import (
    Almacen,
    CategoriaProducto,
    Cliente,
    Producto,
    Ubicacion,
    UnidadMedida,
    Zona,
)
from .services import sync_product_conversion
from .serializers import (
    AlmacenWriteSerializer,
    ClienteWriteSerializer,
    ProductoWriteSerializer,
    UbicacionWriteSerializer,
    ZonaWriteSerializer,
)


MAX_IMPORT_BYTES = 2 * 1024 * 1024
MAX_IMPORT_ROWS = 5000

TEMPLATES = {
    "clientes": [
        "razon_social",
        "ruc",
        "contacto_nombre",
        "contacto_telefono",
        "estado",
    ],
    "productos": [
        "cliente_ruc",
        "sku",
        "codigo_ean",
        "nombre",
        "unidad_codigo",
        "categoria",
        "descripcion",
        "controla_lote",
        "factor_conversion",
        "estado",
    ],
    "almacenes": [
        "codigo",
        "nombre",
        "referencia",
        "capacidad_pallets",
        "estado",
    ],
    "ubicaciones": [
        "almacen_codigo",
        "zona_codigo",
        "zona_nombre",
        "zona_tipo",
        "codigo",
        "pasillo",
        "rack",
        "nivel",
        "posicion",
        "capacidad_volumen",
        "capacidad_peso",
        "estado",
    ],
}


def parse_boolean(value, default=True):
    normalized = str(value or "").strip().lower()
    if not normalized:
        return default
    if normalized in {"1", "true", "si", "sí", "activo", "activa"}:
        return True
    if normalized in {"0", "false", "no", "inactivo", "inactiva"}:
        return False
    raise ValueError("Debe indicar sí/no, true/false o activo/inactivo.")


def _read_rows(uploaded_file, catalog):
    if catalog not in TEMPLATES:
        raise ValidationError(
            {"tipo": ["Selecciona clientes, productos, almacenes o ubicaciones."]}
        )
    if uploaded_file is None:
        raise ValidationError({"archivo": ["Selecciona un archivo CSV."]})
    if uploaded_file.size > MAX_IMPORT_BYTES:
        raise ValidationError({"archivo": ["El archivo no puede superar 2 MB."]})
    if not uploaded_file.name.lower().endswith(".csv"):
        raise ValidationError({"archivo": ["La plantilla debe estar en formato CSV."]})
    try:
        content = uploaded_file.read().decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValidationError(
            {"archivo": ["Guarda el CSV con codificación UTF-8."]}
        ) from exc

    reader = csv.DictReader(io.StringIO(content))
    headers = [str(header or "").strip() for header in (reader.fieldnames or [])]
    missing = [header for header in TEMPLATES[catalog] if header not in headers]
    if missing:
        raise ValidationError(
            {"archivo": [f"Faltan columnas: {', '.join(missing)}."]}
        )
    rows = list(reader)
    if len(rows) > MAX_IMPORT_ROWS:
        raise ValidationError(
            {"archivo": [f"La plantilla admite hasta {MAX_IMPORT_ROWS} filas."]}
        )
    return rows


def _serializer_error(serializer):
    return {
        field: [str(message) for message in messages]
        for field, messages in serializer.errors.items()
    }


def _import_client(row):
    serializer = ClienteWriteSerializer(
        data={
            "razon_social": row.get("razon_social", ""),
            "ruc": row.get("ruc", ""),
            "contacto_nombre": row.get("contacto_nombre", ""),
            "contacto_telefono": row.get("contacto_telefono", ""),
            "estado": parse_boolean(row.get("estado")),
        }
    )
    if not serializer.is_valid():
        raise ValidationError(_serializer_error(serializer))
    now = timezone.now()
    data = serializer.validated_data
    Cliente.objects.create(
        **{
            **data,
            "contacto_nombre": data["contacto_nombre"] or None,
            "contacto_telefono": data["contacto_telefono"] or None,
        },
        fecha_registro=now,
        fecha_actualizacion=now,
    )


def _import_product(row):
    client = Cliente.objects.filter(
        ruc=str(row.get("cliente_ruc", "")).strip(), estado=True
    ).first()
    unit = UnidadMedida.objects.filter(
        codigo__iexact=str(row.get("unidad_codigo", "")).strip(), estado=True
    ).first()
    category_name = str(row.get("categoria", "")).strip()
    category = (
        CategoriaProducto.objects.filter(
            nombre__iexact=category_name, estado=True
        ).first()
        if category_name
        else None
    )
    if client is None:
        raise ValidationError({"cliente_ruc": ["El cliente no existe o está inactivo."]})
    if unit is None:
        raise ValidationError(
            {"unidad_codigo": ["La unidad no existe o está inactiva."]}
        )
    if category_name and category is None:
        raise ValidationError(
            {"categoria": ["La categoría no existe o está inactiva."]}
        )
    serializer = ProductoWriteSerializer(
        data={
            "id_cliente": client.id_cliente,
            "id_categoria": category.id_categoria if category else None,
            "id_unidad_medida": unit.id_unidad_medida,
            "sku": row.get("sku", ""),
            "codigo_ean": row.get("codigo_ean", ""),
            "nombre": row.get("nombre", ""),
            "descripcion": row.get("descripcion", ""),
            "controla_lote": parse_boolean(row.get("controla_lote"), False),
            "factor_conversion": (
                str(row.get("factor_conversion", "")).strip() or None
            ),
            "estado": parse_boolean(row.get("estado")),
        }
    )
    if not serializer.is_valid():
        raise ValidationError(_serializer_error(serializer))
    now = timezone.now()
    data = dict(serializer.validated_data)
    factor_conversion = data.pop("factor_conversion")
    product = Producto.objects.create(
        **data,
        fecha_registro=now,
        fecha_actualizacion=now,
    )
    sync_product_conversion(product, factor_conversion)


def _import_warehouse(row):
    serializer = AlmacenWriteSerializer(
        data={
            "codigo": row.get("codigo", ""),
            "nombre": row.get("nombre", ""),
            "referencia": row.get("referencia", ""),
            "capacidad_pallets": row.get("capacidad_pallets", ""),
            "estado": parse_boolean(row.get("estado")),
        }
    )
    if not serializer.is_valid():
        raise ValidationError(_serializer_error(serializer))
    now = timezone.now()
    data = serializer.validated_data
    Almacen.objects.create(
        **{**data, "referencia": data["referencia"] or None},
        fecha_registro=now,
        fecha_actualizacion=now,
    )


def _import_location(row):
    warehouse = Almacen.objects.filter(
        codigo__iexact=str(row.get("almacen_codigo", "")).strip(), estado=True
    ).first()
    if warehouse is None:
        raise ValidationError(
            {"almacen_codigo": ["El almacén no existe o está inactivo."]}
        )
    zone_code = str(row.get("zona_codigo", "")).strip().upper()
    zone = Zona.objects.filter(
        id_almacen=warehouse.id_almacen, codigo__iexact=zone_code
    ).first()
    if zone is None:
        zone_serializer = ZonaWriteSerializer(
            data={
                "id_almacen": warehouse.id_almacen,
                "codigo": zone_code,
                "nombre": row.get("zona_nombre", ""),
                "tipo": row.get("zona_tipo", ""),
                "estado": True,
            }
        )
        if not zone_serializer.is_valid():
            raise ValidationError(_serializer_error(zone_serializer))
        now = timezone.now()
        zone = Zona.objects.create(
            **zone_serializer.validated_data,
            fecha_registro=now,
            fecha_actualizacion=now,
        )
    elif not zone.estado:
        raise ValidationError({"zona_codigo": ["La zona está inactiva."]})

    serializer = UbicacionWriteSerializer(
        data={
            "id_zona": zone.id_zona,
            "codigo": row.get("codigo", ""),
            "pasillo": row.get("pasillo", ""),
            "rack": row.get("rack", ""),
            "nivel": row.get("nivel", ""),
            "columna": row.get("posicion", ""),
            "posicion": row.get("posicion", ""),
            "capacidad_volumen": row.get("capacidad_volumen", ""),
            "capacidad_peso": row.get("capacidad_peso", ""),
            "estado": parse_boolean(row.get("estado")),
        }
    )
    if not serializer.is_valid():
        raise ValidationError(_serializer_error(serializer))
    now = timezone.now()
    Ubicacion.objects.create(
        **serializer.validated_data,
        fecha_registro=now,
        fecha_actualizacion=now,
    )


IMPORTERS = {
    "clientes": _import_client,
    "productos": _import_product,
    "almacenes": _import_warehouse,
    "ubicaciones": _import_location,
}


def import_master_data(uploaded_file, catalog):
    rows = _read_rows(uploaded_file, catalog)
    loaded = 0
    rejected = []
    for index, row in enumerate(rows, start=2):
        if not any(str(value or "").strip() for value in row.values()):
            continue
        try:
            with transaction.atomic():
                IMPORTERS[catalog](row)
            loaded += 1
        except IntegrityError:
            rejected.append(
                {
                    "fila": index,
                    "errores": {
                        "registro": [
                            "El registro duplica o contradice datos existentes."
                        ]
                    },
                }
            )
        except (ValidationError, ValueError) as exc:
            detail = getattr(exc, "detail", None) or str(exc)
            rejected.append({"fila": index, "errores": detail})
    return {
        "tipo": catalog,
        "procesados": loaded + len(rejected),
        "cargados": loaded,
        "rechazados": len(rejected),
        "detalle_rechazados": rejected,
    }
