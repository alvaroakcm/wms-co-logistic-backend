from decimal import Decimal

from rest_framework import serializers


class MovementLineSerializer(serializers.Serializer):
    id_stock_origen = serializers.IntegerField(min_value=1)
    id_ubicacion_destino = serializers.IntegerField(min_value=1)
    id_pallet_destino = serializers.IntegerField(
        min_value=1, required=False, allow_null=True, default=None
    )
    cantidad = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01")
    )


class MovementCreateSerializer(serializers.Serializer):
    motivo = serializers.CharField(
        max_length=255, trim_whitespace=True, allow_blank=True, default=""
    )
    lineas = MovementLineSerializer(many=True, min_length=1)

    def validate_lineas(self, value):
        stock_ids = [line["id_stock_origen"] for line in value]
        if len(stock_ids) != len(set(stock_ids)):
            raise serializers.ValidationError(
                "No repitas el mismo stock dentro del traslado."
            )
        return value


class RepackingResultSerializer(serializers.Serializer):
    codigo_pallet = serializers.CharField(
        max_length=255, trim_whitespace=True, required=False, allow_blank=True
    )
    cantidad = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01")
    )


class RepackingSerializer(serializers.Serializer):
    id_stock_origen = serializers.IntegerField(min_value=1)
    motivo = serializers.CharField(
        max_length=255, trim_whitespace=True, allow_blank=True, default=""
    )
    fracciones = RepackingResultSerializer(many=True, min_length=2)

    def validate_fracciones(self, value):
        codes = [
            item.get("codigo_pallet", "").strip().upper()
            for item in value
            if item.get("codigo_pallet", "").strip()
        ]
        if len(codes) != len(set(codes)):
            raise serializers.ValidationError(
                "Los códigos de pallet resultantes no pueden repetirse."
            )
        return value
