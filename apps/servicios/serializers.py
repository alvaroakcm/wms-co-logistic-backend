from decimal import Decimal

from rest_framework import serializers

from apps.inventario.models import Stock
from apps.maestros.models import Producto

from .models import Servicio


def _code(value):
    normalized = value.strip().upper()
    if Servicio.objects.filter(codigo__iexact=normalized).exists():
        raise serializers.ValidationError("Ya existe un servicio con este código.")
    return normalized


def _stock_for_client(stock_id, client_id, quantity):
    stock = Stock.objects.filter(id_stock=stock_id).first()
    if stock is None:
        raise serializers.ValidationError({"id_stock": "El stock seleccionado no existe."})
    product = Producto.objects.filter(id_producto=stock.id_producto).first()
    if product is None or product.id_cliente != client_id:
        raise serializers.ValidationError({"id_stock": "El stock no pertenece al cliente seleccionado."})
    available = stock.cantidad_total - stock.cantidad_reservada
    if quantity > available:
        raise serializers.ValidationError({"cantidad": f"La cantidad supera el disponible ({available})."})
    return stock


class RepalletRequestSerializer(serializers.Serializer):
    codigo = serializers.CharField(max_length=50)
    id_cliente = serializers.IntegerField(min_value=1)
    id_stock = serializers.IntegerField(min_value=1)
    descripcion = serializers.CharField(max_length=2000)
    cantidad = serializers.DecimalField(max_digits=12, decimal_places=4, min_value=Decimal("0.0001"))
    cliente_provee_pallet_destino = serializers.BooleanField(default=False)
    tipo_pallet_destino = serializers.CharField(max_length=100, default="Estándar de exportación")
    certificacion_destino = serializers.CharField(max_length=120, allow_blank=True, default="")
    observaciones = serializers.CharField(max_length=2000, allow_blank=True, default="")

    def validate_codigo(self, value):
        return _code(value)

    def validate(self, attrs):
        attrs["stock"] = _stock_for_client(attrs["id_stock"], attrs["id_cliente"], attrs["cantidad"])
        return attrs


class RepalletExecutionSerializer(serializers.Serializer):
    cantidad = serializers.DecimalField(max_digits=12, decimal_places=4, min_value=Decimal("0.0001"))
    numero_paletas = serializers.IntegerField(min_value=1, max_value=10000)
    tarifa = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    codigo_pallet_destino = serializers.CharField(max_length=255)
    tipo_pallet_destino = serializers.CharField(max_length=100, default="Estándar de exportación")
    certificacion_destino = serializers.CharField(max_length=120, allow_blank=True, default="")
    descripcion = serializers.CharField(max_length=2000)
    observaciones = serializers.CharField(max_length=2000, allow_blank=True, default="")

    def validate_codigo_pallet_destino(self, value):
        return value.strip().upper()


class ReboxingSerializer(serializers.Serializer):
    codigo = serializers.CharField(max_length=50)
    id_stock = serializers.IntegerField(min_value=1)
    descripcion = serializers.CharField(max_length=2000)
    cantidad = serializers.DecimalField(max_digits=12, decimal_places=4, min_value=Decimal("0.0001"))
    cantidad_cajas_origen = serializers.IntegerField(min_value=1)
    cantidad_cajas_destino = serializers.IntegerField(min_value=1)
    tarifa = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    observaciones = serializers.CharField(max_length=2000, allow_blank=True, default="")

    def validate_codigo(self, value):
        return _code(value)

    def validate(self, attrs):
        stock = Stock.objects.filter(id_stock=attrs["id_stock"]).first()
        if stock is None:
            raise serializers.ValidationError({"id_stock": "El stock seleccionado no existe."})
        available = stock.cantidad_total - stock.cantidad_reservada
        if attrs["cantidad"] > available:
            raise serializers.ValidationError({"cantidad": f"La cantidad supera el disponible ({available})."})
        product = Producto.objects.filter(id_producto=stock.id_producto).first()
        if product is None:
            raise serializers.ValidationError({"id_stock": "El stock no tiene un producto válido."})
        attrs["stock"] = stock
        attrs["id_cliente"] = product.id_cliente
        return attrs
