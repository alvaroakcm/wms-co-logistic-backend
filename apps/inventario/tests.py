from django.test import SimpleTestCase
from django.urls import resolve

from .serializers import MovementCreateSerializer, RepackingSerializer
from .views import MovementConfirmView, MovementListCreateView, StockListView


class MovementSerializerTests(SimpleTestCase):
    def test_accepts_internal_transfer(self):
        serializer = MovementCreateSerializer(
            data={
                "motivo": "Reabastecimiento de picking",
                "lineas": [
                    {
                        "id_stock_origen": 4,
                        "id_ubicacion_destino": 9,
                        "cantidad": "12.50",
                    }
                ],
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_rejects_duplicate_source_stock(self):
        serializer = MovementCreateSerializer(
            data={
                "lineas": [
                    {
                        "id_stock_origen": 4,
                        "id_ubicacion_destino": 9,
                        "cantidad": "2",
                    },
                    {
                        "id_stock_origen": 4,
                        "id_ubicacion_destino": 10,
                        "cantidad": "3",
                    },
                ]
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("lineas", serializer.errors)


class RepackingSerializerTests(SimpleTestCase):
    def test_accepts_two_resulting_fractions(self):
        serializer = RepackingSerializer(
            data={
                "id_stock_origen": 1,
                "fracciones": [
                    {"codigo_pallet": "PLT-A", "cantidad": "20"},
                    {"codigo_pallet": "PLT-B", "cantidad": "30"},
                ],
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_requires_at_least_two_fractions(self):
        serializer = RepackingSerializer(
            data={
                "id_stock_origen": 1,
                "fracciones": [{"cantidad": "50"}],
            }
        )
        self.assertFalse(serializer.is_valid())


class InventoryUrlTests(SimpleTestCase):
    def test_stock_url_resolves(self):
        self.assertIs(resolve("/api/inventory/stocks/").func.view_class, StockListView)

    def test_movements_url_resolves(self):
        self.assertIs(
            resolve("/api/inventory/movements/").func.view_class,
            MovementListCreateView,
        )

    def test_confirmation_url_resolves(self):
        self.assertIs(
            resolve("/api/inventory/movements/3/confirm/").func.view_class,
            MovementConfirmView,
        )
