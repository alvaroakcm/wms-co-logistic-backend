from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from apps.inventario.models import Lote
from apps.maestros.models import Cliente, Producto


class OrderLineSerializer(serializers.Serializer):
    id_producto = serializers.IntegerField(min_value=1)
    id_lote = serializers.IntegerField(
        min_value=1, required=False, allow_null=True, default=None
    )
    cantidad_solicitada = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01")
    )


class OrderCreateSerializer(serializers.Serializer):
    id_cliente = serializers.IntegerField(min_value=1)
    codigo_documento = serializers.CharField(max_length=255, trim_whitespace=True)
    fecha_programada = serializers.DateField()
    transporte_placa = serializers.CharField(
        max_length=255, allow_blank=True, trim_whitespace=True, default=""
    )
    transporte_conductor = serializers.CharField(
        max_length=255, allow_blank=True, trim_whitespace=True, default=""
    )
    lineas = OrderLineSerializer(many=True, min_length=1)

    def validate_codigo_documento(self, value):
        return value.strip().upper()

    def validate(self, attrs):
        if not Cliente.objects.filter(
            id_cliente=attrs["id_cliente"], estado=True
        ).exists():
            raise serializers.ValidationError(
                {"id_cliente": ["El cliente no existe o está inactivo."]}
            )
        product_ids = [line["id_producto"] for line in attrs["lineas"]]
        products = {
            item.id_producto: item
            for item in Producto.objects.filter(id_producto__in=product_ids)
        }
        lot_ids = {
            line["id_lote"] for line in attrs["lineas"] if line["id_lote"]
        }
        lots = {
            item.id_lote: item
            for item in Lote.objects.filter(id_lote__in=lot_ids)
        }
        seen = set()
        for line in attrs["lineas"]:
            product = products.get(line["id_producto"])
            if (
                not product
                or not product.estado
                or product.id_cliente != attrs["id_cliente"]
            ):
                raise serializers.ValidationError(
                    {"lineas": ["Todos los productos deben pertenecer al cliente y estar activos."]}
                )
            lot = lots.get(line["id_lote"])
            if product.controla_lote:
                if not lot or lot.id_producto != product.id_producto:
                    raise serializers.ValidationError(
                        {"lineas": [f"Selecciona un lote válido para {product.nombre}."]}
                    )
                if lot.fecha_vencimiento and lot.fecha_vencimiento < timezone.localdate():
                    raise serializers.ValidationError(
                        {"lineas": [f"El lote {lot.codigo} está vencido."]}
                    )
            elif line["id_lote"] is not None:
                raise serializers.ValidationError(
                    {"lineas": [f"{product.nombre} no utiliza control por lote."]}
                )
            key = (line["id_producto"], line["id_lote"])
            if key in seen:
                raise serializers.ValidationError(
                    {"lineas": ["No repitas el mismo producto y lote en la guía."]}
                )
            seen.add(key)
        attrs["product_map"] = products
        return attrs


class PreparationLineSerializer(serializers.Serializer):
    id_picking_detalle = serializers.IntegerField(min_value=1)
    cantidad_confirmada = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0")
    )


class PreparationSerializer(serializers.Serializer):
    lineas = PreparationLineSerializer(many=True, min_length=1)

    def validate_lineas(self, value):
        ids = [item["id_picking_detalle"] for item in value]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError("No repitas líneas de preparación.")
        return value


class DispatchCloseSerializer(serializers.Serializer):
    codigo_documento_salida = serializers.CharField(
        max_length=255, trim_whitespace=True
    )
    observaciones = serializers.CharField(
        allow_blank=True, trim_whitespace=True, default=""
    )

    def validate_codigo_documento_salida(self, value):
        return value.strip().upper()


class DispatchIncidentSerializer(serializers.Serializer):
    id_pedido_detalle = serializers.IntegerField(min_value=1)
    tipo = serializers.ChoiceField(
        choices=["FALTANTE", "RETRASO", "ERROR", "DANO", "OTRO"]
    )
    cantidad = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01")
    )
    descripcion = serializers.CharField(
        allow_blank=False, trim_whitespace=True, max_length=2000
    )
