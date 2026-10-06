from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from apps.maestros.models import (
    Cliente,
    Producto,
    ProductoConversion,
    Ubicacion,
    UnidadMedida,
)


class ReceptionLineCreateSerializer(serializers.Serializer):
    id_producto = serializers.IntegerField(min_value=1)
    cantidad_esperada = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.01"),
        required=False,
    )
    cantidad_pallets = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.00"),
        default=Decimal("0.00"),
    )


class ReceptionCreateSerializer(serializers.Serializer):
    id_cliente = serializers.IntegerField(min_value=1)
    codigo_documento = serializers.CharField(
        max_length=255, trim_whitespace=True
    )
    fecha_programada = serializers.DateField()
    transporte_placa = serializers.CharField(
        max_length=255, trim_whitespace=True, allow_blank=True, default=""
    )
    transporte_conductor = serializers.CharField(
        max_length=255, trim_whitespace=True, allow_blank=True, default=""
    )
    transporte_brevete = serializers.CharField(
        max_length=50, trim_whitespace=True, allow_blank=True, default=""
    )
    lineas = ReceptionLineCreateSerializer(many=True, min_length=1)

    def validate_codigo_documento(self, value):
        value = value.strip().upper()
        if not value:
            raise serializers.ValidationError(
                "La guía de remisión es obligatoria."
            )
        return value

    def validate(self, attrs):
        client_id = attrs["id_cliente"]
        if not Cliente.objects.filter(
            id_cliente=client_id, estado=True
        ).exists():
            raise serializers.ValidationError(
                {"id_cliente": ["El cliente no existe o está inactivo."]}
            )

        product_ids = [line["id_producto"] for line in attrs["lineas"]]
        if len(product_ids) != len(set(product_ids)):
            raise serializers.ValidationError(
                {"lineas": ["No repitas un producto dentro de la guía."]}
            )
        products = Producto.objects.filter(id_producto__in=product_ids)
        product_map = {product.id_producto: product for product in products}
        invalid = [
            product_id
            for product_id in product_ids
            if product_id not in product_map
            or not product_map[product_id].estado
            or product_map[product_id].id_cliente != client_id
        ]
        if invalid:
            raise serializers.ValidationError(
                {
                    "lineas": [
                        "Todos los productos deben estar activos y pertenecer al cliente seleccionado."
                    ]
                }
            )
        pallet_unit = UnidadMedida.objects.filter(
            codigo__iexact="PLT", estado=True
        ).first()
        conversions = ProductoConversion.objects.filter(
            id_producto__in=product_ids,
            id_unidad_origen=(
                pallet_unit.id_unidad_medida if pallet_unit else -1
            ),
        )
        conversion_map = {
            conversion.id_producto: conversion for conversion in conversions
        }
        for line in attrs["lineas"]:
            conversion = conversion_map.get(line["id_producto"])
            pallets = line["cantidad_pallets"]
            if conversion:
                if pallets <= 0:
                    raise serializers.ValidationError(
                        {
                            "lineas": [
                                "Indica la cantidad de pallets para los productos configurados por caja."
                            ]
                        }
                    )
                line["cantidad_esperada"] = (
                    pallets * conversion.factor_conversion
                )
            elif "cantidad_esperada" not in line:
                raise serializers.ValidationError(
                    {
                        "lineas": [
                            "Indica la cantidad esperada de cada producto."
                        ]
                    }
                )
            else:
                line["cantidad_pallets"] = Decimal("0.00")
        attrs["product_map"] = product_map
        attrs["conversion_map"] = conversion_map
        return attrs


class ReceptionValidationLineSerializer(serializers.Serializer):
    id_pedido_ingreso_detalle = serializers.IntegerField(min_value=1)
    cantidad_recibida = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.00")
    )
    cantidad_rechazada = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.00"),
        default=Decimal("0.00"),
    )
    observacion = serializers.CharField(
        allow_blank=True, trim_whitespace=True, default=""
    )

    def validate(self, attrs):
        if attrs["cantidad_rechazada"] > attrs["cantidad_recibida"]:
            raise serializers.ValidationError(
                "La cantidad rechazada no puede superar la cantidad recibida."
            )
        return attrs


class ReceptionValidationSerializer(serializers.Serializer):
    documento_verificado = serializers.BooleanField()
    lineas = ReceptionValidationLineSerializer(many=True, min_length=1)

    def validate_documento_verificado(self, value):
        if not value:
            raise serializers.ValidationError(
                "Confirma la validación de la guía de remisión."
            )
        return value

    def validate_lineas(self, value):
        line_ids = [item["id_pedido_ingreso_detalle"] for item in value]
        if len(line_ids) != len(set(line_ids)):
            raise serializers.ValidationError("No repitas líneas de recepción.")
        return value


class LocationAssignmentSerializer(serializers.Serializer):
    id_pedido_ingreso_detalle = serializers.IntegerField(min_value=1)
    id_pedido_ingreso_lote = serializers.IntegerField(
        min_value=1, required=False, allow_null=True, default=None
    )
    id_ubicacion = serializers.IntegerField(min_value=1)
    cantidad = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01")
    )

    def validate_id_ubicacion(self, value):
        if not Ubicacion.objects.filter(
            id_ubicacion=value, estado=True
        ).exists():
            raise serializers.ValidationError(
                "La ubicación no existe o está inactiva."
            )
        return value


class IncidentCreateSerializer(serializers.Serializer):
    id_pedido_ingreso_detalle = serializers.IntegerField(min_value=1)
    tipo = serializers.ChoiceField(
        choices=("DIFERENCIA", "DANO", "DOCUMENTO", "CALIDAD", "OTRO")
    )
    descripcion = serializers.CharField(trim_whitespace=True)
    cantidad_afectada = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01")
    )

    def validate_descripcion(self, value):
        if not value.strip():
            raise serializers.ValidationError("Describe la incidencia detectada.")
        return value.strip()


class ReceptionLotSerializer(serializers.Serializer):
    codigo = serializers.CharField(max_length=255, trim_whitespace=True)
    fecha_fabricacion = serializers.DateField(required=False, allow_null=True)
    fecha_vencimiento = serializers.DateField()
    cantidad = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01")
    )

    def validate_codigo(self, value):
        return value.strip().upper()

    def validate(self, attrs):
        manufacture = attrs.get("fecha_fabricacion")
        expiration = attrs["fecha_vencimiento"]
        if manufacture and expiration < manufacture:
            raise serializers.ValidationError(
                "La fecha de vencimiento no puede ser anterior a la fabricación."
            )
        if expiration < timezone.localdate():
            raise serializers.ValidationError(
                "No se puede recibir un lote con fecha de vencimiento pasada."
            )
        return attrs


class ReceptionLotsSerializer(serializers.Serializer):
    id_pedido_ingreso_detalle = serializers.IntegerField(min_value=1)
    lotes = ReceptionLotSerializer(many=True, min_length=1)

    def validate_lotes(self, value):
        codes = [item["codigo"] for item in value]
        if len(codes) != len(set(codes)):
            raise serializers.ValidationError(
                "No repitas el mismo lote para este producto."
            )
        return value
