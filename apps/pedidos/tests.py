from django.test import SimpleTestCase
from django.urls import resolve

from .serializers import (
    DispatchCloseSerializer,
    DispatchIncidentSerializer,
    PreparationSerializer,
)
from .views import (
    DispatchHistoryView,
    DispatchIncidentView,
    OrderCancelView,
    OrderDispatchView,
    OrderDocumentView,
    OrderListCreateView,
    OrderPreparationView,
)


class PreparationSerializerTests(SimpleTestCase):
    def test_accepts_verified_quantities(self):
        serializer = PreparationSerializer(
            data={
                "lineas": [
                    {"id_picking_detalle": 1, "cantidad_confirmada": "12"},
                    {"id_picking_detalle": 2, "cantidad_confirmada": "8"},
                ]
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_rejects_duplicate_picking_lines(self):
        serializer = PreparationSerializer(
            data={
                "lineas": [
                    {"id_picking_detalle": 1, "cantidad_confirmada": "2"},
                    {"id_picking_detalle": 1, "cantidad_confirmada": "2"},
                ]
            }
        )
        self.assertFalse(serializer.is_valid())


class DispatchSerializerTests(SimpleTestCase):
    def test_normalizes_document_code(self):
        serializer = DispatchCloseSerializer(
            data={"codigo_documento_salida": " t001-0009 ", "observaciones": ""}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data["codigo_documento_salida"], "T001-0009"
        )

    def test_accepts_dispatch_incident(self):
        serializer = DispatchIncidentSerializer(
            data={
                "id_pedido_detalle": 3,
                "tipo": "FALTANTE",
                "cantidad": "2",
                "descripcion": "Dos cajas no llegaron al muelle.",
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_rejects_unknown_incident_type(self):
        serializer = DispatchIncidentSerializer(
            data={
                "id_pedido_detalle": 3,
                "tipo": "DESCONOCIDO",
                "cantidad": "2",
                "descripcion": "Detalle",
            }
        )
        self.assertFalse(serializer.is_valid())


class OrderUrlTests(SimpleTestCase):
    def test_order_collection_resolves(self):
        self.assertIs(resolve("/api/orders/").func.view_class, OrderListCreateView)

    def test_preparation_url_resolves(self):
        self.assertIs(
            resolve("/api/orders/2/prepare/").func.view_class,
            OrderPreparationView,
        )

    def test_dispatch_url_resolves(self):
        self.assertIs(
            resolve("/api/orders/2/dispatch/").func.view_class,
            OrderDispatchView,
        )

    def test_cancel_url_resolves(self):
        self.assertIs(
            resolve("/api/orders/2/cancel/").func.view_class,
            OrderCancelView,
        )

    def test_document_url_resolves(self):
        self.assertIs(
            resolve("/api/orders/2/document/").func.view_class,
            OrderDocumentView,
        )

    def test_dispatch_incident_url_resolves(self):
        self.assertIs(
            resolve("/api/orders/2/dispatch/incidents/").func.view_class,
            DispatchIncidentView,
        )

    def test_dispatch_history_url_resolves(self):
        self.assertIs(
            resolve("/api/dispatches/history/").func.view_class,
            DispatchHistoryView,
        )
