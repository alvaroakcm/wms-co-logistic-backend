from io import BytesIO
from datetime import date
from unittest.mock import patch
from zipfile import ZipFile

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from .exports import build_pdf, build_xlsx
from .planning import _build_series
from .views import CapacityPlanningView, DashboardReportView, ExportReportView


class ReportExportTests(SimpleTestCase):
    def test_xlsx_is_a_valid_workbook(self):
        payload = build_xlsx("Inventario", ["SKU", "Cantidad"], [["SKU-01", 12]])
        with ZipFile(BytesIO(payload)) as archive:
            self.assertIn("xl/worksheets/sheet1.xml", archive.namelist())
            self.assertIn(b"SKU-01", archive.read("xl/worksheets/sheet1.xml"))

    def test_pdf_has_valid_header_and_content(self):
        payload = build_pdf("Reporte WMS", ["SKU", "Cantidad"], [["SKU-01", 12]])
        self.assertTrue(payload.startswith(b"%PDF-1.4"))
        self.assertIn(b"Reporte WMS", payload)


class ReportViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = type("User", (), {"id": "00000000-0000-0000-0000-000000000001", "is_authenticated": True})()

    @patch("apps.reportes.views.require_application_permission")
    @patch("apps.reportes.views.dashboard_report")
    def test_dashboard_validates_and_returns_service_payload(self, service, permission):
        service.return_value = {"kpis": {"recepciones": 2}}
        request = self.factory.get("/api/reports/dashboard/?fecha_desde=2026-09-01&fecha_hasta=2026-09-30")
        force_authenticate(request, user=self.user)
        response = DashboardReportView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["kpis"]["recepciones"], 2)
        permission.assert_called_once_with(self.user, "reportes.ver")

    @patch("apps.reportes.views.require_application_permission")
    @patch("apps.reportes.views.export_dataset")
    def test_export_endpoint_returns_excel_download(self, dataset, permission):
        dataset.return_value = ("Inventario", ["SKU"], [["SKU-01"]])
        request = self.factory.get("/api/reports/export/?tipo=inventario&formato=xlsx")
        force_authenticate(request, user=self.user)
        response = ExportReportView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Report-Rows"], "1")
        self.assertTrue(response.content.startswith(b"PK"))

    @patch("apps.reportes.views.require_application_permission")
    def test_export_rejects_unknown_report(self, permission):
        request = self.factory.get("/api/reports/export/?tipo=desconocido")
        force_authenticate(request, user=self.user)
        response = ExportReportView.as_view()(request)
        self.assertEqual(response.status_code, 400)

    @patch("apps.reportes.views.require_application_permission")
    @patch("apps.reportes.views.capacity_plan")
    def test_capacity_planning_validates_threshold_and_period(self, service, permission):
        service.return_value = {"almacenes": [], "alertas": []}
        request = self.factory.get("/api/planning/capacity/?fecha_desde=2026-11-01&fecha_hasta=2026-11-30&umbral=90")
        force_authenticate(request, user=self.user)
        response = CapacityPlanningView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        service.assert_called_once_with(date(2026, 11, 1), date(2026, 11, 30), "", "", 90)


class CapacityProjectionTests(SimpleTestCase):
    def test_projection_marks_threshold_and_compares_actual(self):
        events = {
            date(2026, 11, 1): {"planned_in": 20, "actual_in": 18},
            date(2026, 11, 2): {"planned_out": 5, "actual_out": 4},
        }
        rows, alerts = _build_series(
            100, 70, events, date(2026, 11, 1), date(2026, 11, 2), 85,
            today=date(2026, 11, 2),
        )
        self.assertEqual(rows[0]["porcentaje_planificado"], 90)
        self.assertEqual(rows[1]["diferencia"], -1)
        self.assertEqual(len(alerts), 2)

    def test_future_actual_values_are_hidden(self):
        rows, _ = _build_series(
            100, 40, {}, date(2026, 11, 2), date(2026, 11, 2), 85,
            today=date(2026, 11, 1),
        )
        self.assertIsNone(rows[0]["ocupacion_real"])
