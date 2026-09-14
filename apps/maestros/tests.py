from contextlib import nullcontext
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory, force_authenticate

from .importers import IMPORTERS, import_master_data
from .serializers import (
    AlmacenWriteSerializer,
    ClienteWriteSerializer,
    ProductoWriteSerializer,
)
from .services import calculate_product_boxes
from .views import ProductoDetailView, UbicacionDetailView


class ClienteSerializerTests(SimpleTestCase):
    def test_ruc_must_have_exactly_eleven_digits(self):
        serializer = ClienteWriteSerializer(
            data={
                "razon_social": "Cliente de prueba",
                "ruc": "ABC123",
                "contacto_nombre": "",
                "contacto_telefono": "",
                "estado": True,
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("ruc", serializer.errors)

    @patch("apps.maestros.serializers.Cliente.objects.filter")
    def test_duplicate_ruc_is_rejected(self, client_filter):
        client_filter.return_value.exists.return_value = True
        serializer = ClienteWriteSerializer(
            data={
                "razon_social": "Cliente de prueba",
                "ruc": "20123456789",
                "contacto_nombre": "Ana",
                "contacto_telefono": "+51 999 999 999",
                "estado": True,
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertEqual(
            str(serializer.errors["ruc"][0]),
            "Ya existe un cliente con este RUC.",
        )


class ProductoSerializerTests(SimpleTestCase):
    def test_ean_must_have_eight_or_thirteen_digits(self):
        serializer = ProductoWriteSerializer(
            data={
                "id_cliente": 1,
                "id_unidad_medida": 1,
                "id_categoria": None,
                "sku": "SKU-001",
                "codigo_ean": "123",
                "nombre": "Producto",
                "descripcion": "",
                "controla_lote": False,
                "estado": True,
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("codigo_ean", serializer.errors)

    @patch("apps.maestros.serializers.UnidadMedida.objects.filter")
    @patch("apps.maestros.serializers.Cliente.objects.filter")
    def test_box_product_requires_conversion_factor(self, client_filter, unit_filter):
        client_filter.return_value.exists.return_value = True
        unit_filter.return_value.first.return_value = SimpleNamespace(codigo="CJ")
        serializer = ProductoWriteSerializer(
            data={
                "id_cliente": 1,
                "id_unidad_medida": 2,
                "id_categoria": None,
                "sku": "SKU-BOX",
                "codigo_ean": "12345678",
                "nombre": "Producto por caja",
                "descripcion": "",
                "controla_lote": False,
                "estado": True,
                "factor_conversion": None,
            },
            context={"current_client_id": 1, "current_unit_id": 2},
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("factor_conversion", serializer.errors)

    @patch("apps.maestros.services.ProductoConversion.objects.filter")
    @patch("apps.maestros.services.UnidadMedida.objects.filter")
    def test_calculates_boxes_from_pallets(self, unit_filter, conversion_filter):
        unit_filter.return_value.first.return_value = SimpleNamespace(
            id_unidad_medida=4
        )
        conversion_filter.return_value.first.return_value = SimpleNamespace(
            factor_conversion=Decimal("24.00")
        )

        result = calculate_product_boxes(
            SimpleNamespace(id_producto=7, id_unidad_medida=2),
            Decimal("3.00"),
        )

        self.assertEqual(result, Decimal("72.0000"))


class ProductoUpdateViewTests(SimpleTestCase):
    @patch("apps.maestros.views.require_application_permission")
    @patch("apps.maestros.views.get_object_or_404")
    @patch("apps.maestros.views.ProductoWriteSerializer")
    @patch("apps.maestros.views.transaction.atomic", side_effect=nullcontext)
    @patch("apps.maestros.views.serialize_products")
    def test_update_preserves_product_identity(
        self, serialize, _, serializer_class, get_product, require_permission
    ):
        product = SimpleNamespace(
            id_producto=7,
            id_cliente=1,
            id_categoria=None,
            id_unidad_medida=1,
            save=Mock(),
        )
        get_product.return_value = product
        serializer_class.return_value.validated_data = {
            "id_cliente": 1,
            "id_categoria": None,
            "id_unidad_medida": 1,
            "sku": "SKU-001",
            "codigo_ean": "1234567890123",
            "nombre": "Producto actualizado",
            "descripcion": "",
            "controla_lote": False,
            "estado": True,
        }
        serialize.return_value = [{"id_producto": 7}]
        request = APIRequestFactory().patch(
            "/api/products/7/",
            serializer_class.return_value.validated_data,
            format="json",
        )
        force_authenticate(
            request,
            user=SimpleNamespace(id="user-id", is_authenticated=True),
            token="valid-token",
        )

        with patch("apps.maestros.views.sync_product_conversion") as sync_conversion:
            response = ProductoDetailView.as_view()(request, product_id=7)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id_producto"], 7)
        self.assertEqual(product.id_producto, 7)
        product.save.assert_called_once()
        sync_conversion.assert_called_once_with(product, None)
        require_permission.assert_called_once()


class AlmacenSerializerTests(SimpleTestCase):
    @patch("apps.maestros.serializers.Almacen.objects.filter")
    def test_duplicate_warehouse_code_is_rejected(self, warehouse_filter):
        warehouse_filter.return_value.exists.return_value = True
        serializer = AlmacenWriteSerializer(
            data={
                "codigo": "ALM-01",
                "nombre": "Almacén principal",
                "referencia": "Lima",
                "capacidad_pallets": 50,
                "estado": True,
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("codigo", serializer.errors)


class UbicacionUpdateViewTests(SimpleTestCase):
    @patch("apps.maestros.views.require_application_permission")
    @patch("apps.maestros.views.get_object_or_404")
    @patch("apps.maestros.views.UbicacionWriteSerializer")
    @patch("apps.maestros.views.Stock.objects.filter")
    def test_location_with_active_stock_cannot_be_disabled(
        self, stock_filter, serializer_class, get_location, require_permission
    ):
        location = SimpleNamespace(
            id_ubicacion=9,
            id_zona=2,
            estado=True,
            save=Mock(),
        )
        get_location.return_value = location
        serializer_class.return_value.validated_data = {
            "id_zona": 2,
            "codigo": "UBI-01",
            "pasillo": "1",
            "rack": "A",
            "nivel": "1",
            "columna": "1",
            "posicion": "1",
            "capacidad_volumen": "10.00",
            "capacidad_peso": "500.00",
            "estado": False,
        }
        stock_filter.return_value.exists.return_value = True
        request = APIRequestFactory().patch(
            "/api/locations/9/",
            serializer_class.return_value.validated_data,
            format="json",
        )
        force_authenticate(
            request,
            user=SimpleNamespace(id="user-id", is_authenticated=True),
            token="valid-token",
        )

        response = UbicacionDetailView.as_view()(request, location_id=9)

        self.assertEqual(response.status_code, 400)
        self.assertIn("stock activo", str(response.data["estado"][0]))
        location.save.assert_not_called()
        require_permission.assert_called_once()


class MasterDataImportTests(SimpleTestCase):
    @patch("apps.maestros.importers.transaction.atomic", side_effect=nullcontext)
    def test_import_report_separates_loaded_and_rejected_rows(self, _):
        importer = Mock(side_effect=[None, ValidationError({"ruc": ["Duplicado"]})])
        content = (
            "razon_social,ruc,contacto_nombre,contacto_telefono,estado\n"
            "Cliente Uno,20123456789,Ana,999999999,activo\n"
            "Cliente Dos,20123456789,Luis,988888888,activo\n"
        )
        upload = SimpleUploadedFile(
            "clientes.csv", content.encode("utf-8"), content_type="text/csv"
        )

        with patch.dict(IMPORTERS, {"clientes": importer}):
            report = import_master_data(upload, "clientes")

        self.assertEqual(report["procesados"], 2)
        self.assertEqual(report["cargados"], 1)
        self.assertEqual(report["rechazados"], 1)
        self.assertEqual(report["detalle_rechazados"][0]["fila"], 3)
