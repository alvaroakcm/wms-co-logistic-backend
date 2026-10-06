from django.urls import path

from .views import CapacityPlanningView, DashboardReportView, ExportReportView, MovementReportView, OccupancyReportView, TraceabilityReportView


urlpatterns = [
    path("reports/dashboard/", DashboardReportView.as_view(), name="reports-dashboard"),
    path("reports/occupancy/", OccupancyReportView.as_view(), name="reports-occupancy"),
    path("reports/movements/", MovementReportView.as_view(), name="reports-movements"),
    path("reports/traceability/", TraceabilityReportView.as_view(), name="reports-traceability"),
    path("reports/export/", ExportReportView.as_view(), name="reports-export"),
    path("planning/capacity/", CapacityPlanningView.as_view(), name="planning-capacity"),
]
