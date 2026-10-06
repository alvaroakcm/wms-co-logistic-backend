from django.http import HttpResponse
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.usuarios.permissions import require_application_permission

from .exports import build_pdf, build_xlsx
from .services import dashboard_report, export_dataset, movement_report, occupancy_report, traceability_report
from .planning import capacity_plan


def _date(request, name):
    value = request.query_params.get(name, "").strip()
    if not value:
        return None
    try:
        return timezone.datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValidationError({name: ["La fecha debe utilizar el formato AAAA-MM-DD."]}) from exc


def _filters(request):
    return {
        "fecha_desde": _date(request, "fecha_desde"),
        "fecha_hasta": _date(request, "fecha_hasta"),
        "producto": request.query_params.get("producto", "").strip(),
        "cliente": request.query_params.get("cliente", "").strip(),
        "ubicacion": request.query_params.get("ubicacion", "").strip(),
        "responsable": request.query_params.get("responsable", "").strip(),
        "tipo": request.query_params.get("tipo_operacion", request.query_params.get("tipo", "")).strip(),
        "estado": request.query_params.get("estado", "").strip(),
        "almacen": request.query_params.get("almacen", "").strip(),
        "lote": request.query_params.get("lote", "").strip(),
    }


def _validate_period(filters):
    if filters["fecha_desde"] and filters["fecha_hasta"] and filters["fecha_desde"] > filters["fecha_hasta"]:
        raise ValidationError({"fecha_hasta": ["La fecha final debe ser posterior a la inicial."]})


class DashboardReportView(APIView):
    def get(self, request):
        require_application_permission(request.user, "reportes.ver")
        filters = _filters(request)
        _validate_period(filters)
        return Response(dashboard_report(filters["fecha_desde"], filters["fecha_hasta"], filters["almacen"]))


class OccupancyReportView(APIView):
    def get(self, request):
        require_application_permission(request.user, "reportes.ver")
        return Response(occupancy_report(request.query_params.get("almacen", "").strip()))


class MovementReportView(APIView):
    def get(self, request):
        require_application_permission(request.user, "reportes.ver")
        filters = _filters(request)
        _validate_period(filters)
        return Response(movement_report(filters))


class TraceabilityReportView(APIView):
    def get(self, request):
        require_application_permission(request.user, "trazabilidad.ver")
        return Response(traceability_report(
            request.query_params.get("producto", "").strip(),
            request.query_params.get("lote", "").strip(),
            request.query_params.get("cliente", "").strip(),
        ))


class ExportReportView(APIView):
    def get(self, request):
        require_application_permission(request.user, "reportes.exportar")
        report_type = request.query_params.get("tipo", "").strip().lower()
        file_format = request.query_params.get("formato", "xlsx").strip().lower()
        if report_type not in {"inventario", "recepciones", "movimientos", "despachos", "ocupacion", "trazabilidad"}:
            raise ValidationError({"tipo": ["Selecciona un reporte válido."]})
        if file_format not in {"pdf", "xlsx"}:
            raise ValidationError({"formato": ["El formato debe ser pdf o xlsx."]})
        filters = _filters(request)
        _validate_period(filters)
        title, headers, rows = export_dataset(report_type, filters)
        if file_format == "pdf":
            content = build_pdf(f"WMS - {title}", headers, rows)
            content_type = "application/pdf"
        else:
            content = build_xlsx(title, headers, rows)
            content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        response = HttpResponse(content, content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="wms-{report_type}.{file_format}"'
        response["X-Report-Rows"] = str(len(rows))
        return response


class CapacityPlanningView(APIView):
    def get(self, request):
        require_application_permission(request.user, "planificacion.ver")
        filters = _filters(request)
        _validate_period(filters)
        date_from = filters["fecha_desde"] or timezone.localdate()
        date_to = filters["fecha_hasta"] or date_from + timezone.timedelta(days=30)
        if (date_to - date_from).days > 366:
            raise ValidationError({"fecha_hasta": ["El periodo máximo de planificación es de 366 días."]})
        try:
            threshold = int(request.query_params.get("umbral", "85"))
        except ValueError as exc:
            raise ValidationError({"umbral": ["El umbral debe ser un número entero."]}) from exc
        if threshold < 1 or threshold > 100:
            raise ValidationError({"umbral": ["El umbral debe estar entre 1 y 100."]})
        return Response(capacity_plan(
            date_from,
            date_to,
            filters["almacen"],
            filters["cliente"],
            threshold,
        ))
