from datetime import timedelta

from django.test import SimpleTestCase
from django.urls import resolve
from django.utils import timezone

from .serializers import (
    IncidentCreateSerializer,
    ReceptionLotsSerializer,
    ReceptionValidationSerializer,
)
from .views import (
    ReceptionDocumentView,
    ReceptionListCreateView,
    ReceptionLotsView,
)


class ReceptionValidationSerializerTests(SimpleTestCase):
    def test_requires_document_confirmation(self):
        serializer = ReceptionValidationSerializer(
            data={
                "documento_verificado": False,
                "lineas": [
                    {
                        "id_pedido_ingreso_detalle": 1,
                        "cantidad_recibida": "10",
                        "cantidad_rechazada": "0",
                        "observacion": "",
                    }
                ],
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("documento_verificado", serializer.errors)

    def test_rejected_quantity_cannot_exceed_received_quantity(self):
        serializer = ReceptionValidationSerializer(
            data={
                "documento_verificado": True,
                "lineas": [
                    {
                        "id_pedido_ingreso_detalle": 1,
                        "cantidad_recibida": "2",
                        "cantidad_rechazada": "3",
                        "observacion": "Daño",
                    }
                ],
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("lineas", serializer.errors)

    def test_rejects_duplicate_detail_lines(self):
        serializer = ReceptionValidationSerializer(
            data={
                "documento_verificado": True,
                "lineas": [
                    {
                        "id_pedido_ingreso_detalle": 1,
                        "cantidad_recibida": "2",
                        "cantidad_rechazada": "0",
                    },
                    {
                        "id_pedido_ingreso_detalle": 1,
                        "cantidad_recibida": "2",
                        "cantidad_rechazada": "0",
                    },
                ],
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("lineas", serializer.errors)


class IncidentSerializerTests(SimpleTestCase):
    def test_accepts_complete_incident(self):
        serializer = IncidentCreateSerializer(
            data={
                "id_pedido_ingreso_detalle": 4,
                "tipo": "DANO",
                "descripcion": "Caja golpeada durante la descarga.",
                "cantidad_afectada": "2",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)


class ReceptionUrlTests(SimpleTestCase):
    def test_receipt_collection_resolves_to_api_view(self):
        match = resolve("/api/receipts/")

        self.assertIs(match.func.view_class, ReceptionListCreateView)

    def test_printable_document_url_resolves(self):
        match = resolve("/api/receipts/8/document/")

        self.assertIs(match.func.view_class, ReceptionDocumentView)

    def test_lots_url_resolves(self):
        match = resolve("/api/receipts/8/lots/")

        self.assertIs(match.func.view_class, ReceptionLotsView)


class ReceptionLotsSerializerTests(SimpleTestCase):
    def test_accepts_multiple_coherent_lots(self):
        today = timezone.localdate()
        serializer = ReceptionLotsSerializer(
            data={
                "id_pedido_ingreso_detalle": 4,
                "lotes": [
                    {
                        "codigo": "lot-001",
                        "fecha_fabricacion": str(today),
                        "fecha_vencimiento": str(today + timedelta(days=30)),
                        "cantidad": "3",
                    },
                    {
                        "codigo": "lot-002",
                        "fecha_vencimiento": str(today + timedelta(days=60)),
                        "cantidad": "2",
                    },
                ],
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["lotes"][0]["codigo"], "LOT-001")

    def test_rejects_expired_lot(self):
        serializer = ReceptionLotsSerializer(
            data={
                "id_pedido_ingreso_detalle": 4,
                "lotes": [
                    {
                        "codigo": "LOT-OLD",
                        "fecha_vencimiento": str(
                            timezone.localdate() - timedelta(days=1)
                        ),
                        "cantidad": "1",
                    }
                ],
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("lotes", serializer.errors)

    def test_rejects_duplicate_lot_codes(self):
        expiration = timezone.localdate() + timedelta(days=30)
        serializer = ReceptionLotsSerializer(
            data={
                "id_pedido_ingreso_detalle": 4,
                "lotes": [
                    {
                        "codigo": "LOT-001",
                        "fecha_vencimiento": str(expiration),
                        "cantidad": "1",
                    },
                    {
                        "codigo": "lot-001",
                        "fecha_vencimiento": str(expiration),
                        "cantidad": "1",
                    },
                ],
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("lotes", serializer.errors)
