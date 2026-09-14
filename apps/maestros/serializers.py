import re
from decimal import Decimal

from rest_framework import serializers

from .models import (
    Almacen,
    CategoriaProducto,
    Cliente,
    Producto,
    Ubicacion,
    UnidadMedida,
    Zona,
)


def _clean(value):
    return value.strip()


class ClienteWriteSerializer(serializers.Serializer):
    razon_social = serializers.CharField(max_length=150, trim_whitespace=True)
    ruc = serializers.RegexField(r"^\d{11}$", max_length=11)
    contacto_nombre = serializers.CharField(
        max_length=100, trim_whitespace=True, allow_blank=True, default=""
    )
    contacto_telefono = serializers.CharField(
        max_length=20, trim_whitespace=True, allow_blank=True, default=""
    )
    estado = serializers.BooleanField(default=True)

    def validate_razon_social(self, value):
        return _clean(value)

    def validate_ruc(self, value):
        client_id = self.context.get("client_id")
        query = Cliente.objects.filter(ruc=value)
        if client_id is not None:
            query = query.exclude(id_cliente=client_id)
        if query.exists():
            raise serializers.ValidationError("Ya existe un cliente con este RUC.")
        return value

    def validate_contacto_nombre(self, value):
        return _clean(value)

    def validate_contacto_telefono(self, value):
        cleaned = _clean(value)
        if cleaned and not re.fullmatch(r"[0-9+()\-\s]{6,20}", cleaned):
            raise serializers.ValidationError(
                "Ingresa un teléfono válido de entre 6 y 20 caracteres."
            )
        return cleaned


class ProductoWriteSerializer(serializers.Serializer):
    id_cliente = serializers.IntegerField(min_value=1)
    id_categoria = serializers.IntegerField(
        min_value=1, allow_null=True, required=False, default=None
    )
    id_unidad_medida = serializers.IntegerField(min_value=1)
    sku = serializers.CharField(max_length=50, trim_whitespace=True)
    codigo_ean = serializers.RegexField(r"^(\d{8}|\d{13})$", max_length=13)
    nombre = serializers.CharField(max_length=150, trim_whitespace=True)
    descripcion = serializers.CharField(
        allow_blank=True, allow_null=True, required=False, default=""
    )
    controla_lote = serializers.BooleanField(default=False)
    estado = serializers.BooleanField(default=True)
    factor_conversion = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
        allow_null=True,
        required=False,
        default=None,
    )

    def validate_sku(self, value):
        return _clean(value).upper()

    def validate_nombre(self, value):
        return _clean(value)

    def validate_descripcion(self, value):
        return _clean(value or "")

    def validate(self, attrs):
        product_id = self.context.get("product_id")

        client_query = Cliente.objects.filter(id_cliente=attrs["id_cliente"])
        if attrs["id_cliente"] != self.context.get("current_client_id"):
            client_query = client_query.filter(estado=True)
        if not client_query.exists():
            raise serializers.ValidationError(
                {"id_cliente": ["El cliente no existe o está inactivo."]}
            )
        unit_query = UnidadMedida.objects.filter(
            id_unidad_medida=attrs["id_unidad_medida"]
        )
        if attrs["id_unidad_medida"] != self.context.get("current_unit_id"):
            unit_query = unit_query.filter(estado=True)
        unit = unit_query.first()
        if unit is None:
            raise serializers.ValidationError(
                {"id_unidad_medida": ["La unidad no existe o está inactiva."]}
            )
        unit_code = unit.codigo.strip().upper()
        if unit_code not in {"CJ", "UND"}:
            raise serializers.ValidationError(
                {
                    "id_unidad_medida": [
                        "La unidad comercial debe ser Caja (CJ) o Unidad (UND)."
                    ]
                }
            )
        factor = attrs.get("factor_conversion")
        if unit_code == "CJ" and factor is None:
            raise serializers.ValidationError(
                {
                    "factor_conversion": [
                        "Indica cuántas cajas contiene cada pallet."
                    ]
                }
            )
        if unit_code == "CJ" and not UnidadMedida.objects.filter(
            codigo__iexact="PLT", estado=True
        ).exists():
            raise serializers.ValidationError(
                {
                    "factor_conversion": [
                        "La unidad Pallet (PLT) no está configurada o está inactiva."
                    ]
                }
            )
        if unit_code == "UND" and factor is not None:
            raise serializers.ValidationError(
                {
                    "factor_conversion": [
                        "Los productos por unidad no utilizan pallets ni factor de conversión."
                    ]
                }
            )
        if attrs["id_categoria"] is not None:
            category_query = CategoriaProducto.objects.filter(
                id_categoria=attrs["id_categoria"]
            )
            if attrs["id_categoria"] != self.context.get("current_category_id"):
                category_query = category_query.filter(estado=True)
            if not category_query.exists():
                raise serializers.ValidationError(
                    {"id_categoria": ["La categoría no existe o está inactiva."]}
                )

        sku_query = Producto.objects.filter(
            id_cliente=attrs["id_cliente"], sku__iexact=attrs["sku"]
        )
        ean_query = Producto.objects.filter(codigo_ean=attrs["codigo_ean"])
        if product_id is not None:
            sku_query = sku_query.exclude(id_producto=product_id)
            ean_query = ean_query.exclude(id_producto=product_id)
        errors = {}
        if sku_query.exists():
            errors["sku"] = ["Ya existe este SKU para el cliente seleccionado."]
        if ean_query.exists():
            errors["codigo_ean"] = ["Ya existe un producto con este código EAN."]
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class ProductoConversionCalculationSerializer(serializers.Serializer):
    cantidad_pallets = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.00"),
    )


class AlmacenWriteSerializer(serializers.Serializer):
    codigo = serializers.CharField(max_length=20, trim_whitespace=True)
    nombre = serializers.CharField(max_length=100, trim_whitespace=True)
    referencia = serializers.CharField(
        max_length=150, trim_whitespace=True, allow_blank=True, default=""
    )
    capacidad_pallets = serializers.IntegerField(min_value=0)
    estado = serializers.BooleanField(default=True)

    def validate_codigo(self, value):
        code = _clean(value).upper()
        query = Almacen.objects.filter(codigo__iexact=code)
        warehouse_id = self.context.get("warehouse_id")
        if warehouse_id is not None:
            query = query.exclude(id_almacen=warehouse_id)
        if query.exists():
            raise serializers.ValidationError(
                "Ya existe un almacén con este código."
            )
        return code

    def validate_nombre(self, value):
        return _clean(value)

    def validate_referencia(self, value):
        return _clean(value)


class ZonaWriteSerializer(serializers.Serializer):
    id_almacen = serializers.IntegerField(min_value=1)
    codigo = serializers.CharField(max_length=20, trim_whitespace=True)
    nombre = serializers.CharField(max_length=100, trim_whitespace=True)
    tipo = serializers.CharField(max_length=50, trim_whitespace=True)
    estado = serializers.BooleanField(default=True)

    def validate_codigo(self, value):
        return _clean(value).upper()

    def validate_nombre(self, value):
        return _clean(value)

    def validate_tipo(self, value):
        return _clean(value)

    def validate(self, attrs):
        if not Almacen.objects.filter(
            id_almacen=attrs["id_almacen"], estado=True
        ).exists():
            raise serializers.ValidationError(
                {"id_almacen": ["El almacén no existe o está inactivo."]}
            )
        query = Zona.objects.filter(
            id_almacen=attrs["id_almacen"], codigo__iexact=attrs["codigo"]
        )
        zone_id = self.context.get("zone_id")
        if zone_id is not None:
            query = query.exclude(id_zona=zone_id)
        if query.exists():
            raise serializers.ValidationError(
                {"codigo": ["Ya existe esta zona dentro del almacén."]}
            )
        return attrs


class UbicacionWriteSerializer(serializers.Serializer):
    id_zona = serializers.IntegerField(min_value=1)
    codigo = serializers.CharField(max_length=50, trim_whitespace=True)
    pasillo = serializers.CharField(max_length=10, trim_whitespace=True)
    rack = serializers.CharField(max_length=10, trim_whitespace=True)
    nivel = serializers.CharField(max_length=10, trim_whitespace=True)
    columna = serializers.CharField(max_length=10, trim_whitespace=True)
    posicion = serializers.CharField(max_length=10, trim_whitespace=True)
    capacidad_volumen = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=0
    )
    capacidad_peso = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=0
    )
    estado = serializers.BooleanField(default=True)

    def validate_codigo(self, value):
        code = _clean(value).upper()
        query = Ubicacion.objects.filter(codigo__iexact=code)
        location_id = self.context.get("location_id")
        if location_id is not None:
            query = query.exclude(id_ubicacion=location_id)
        if query.exists():
            raise serializers.ValidationError(
                "Ya existe una ubicación con este código."
            )
        return code

    def validate(self, attrs):
        zone_query = Zona.objects.filter(id_zona=attrs["id_zona"])
        if attrs["id_zona"] != self.context.get("current_zone_id"):
            zone_query = zone_query.filter(estado=True)
        zone = zone_query.first()
        if zone is None:
            raise serializers.ValidationError(
                {"id_zona": ["La zona no existe o está inactiva."]}
            )
        if not Almacen.objects.filter(
            id_almacen=zone.id_almacen, estado=True
        ).exists():
            raise serializers.ValidationError(
                {"id_zona": ["El almacén de la zona está inactivo."]}
            )
        return attrs
