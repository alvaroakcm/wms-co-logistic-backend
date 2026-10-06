from django.urls import path

from .views import (
    ReceptionDetailView,
    ReceptionDocumentView,
    ReceptionIncidentCreateView,
    ReceptionListCreateView,
    ReceptionLocationAssignmentView,
    ReceptionLotsView,
    ReceptionOptionsView,
    ReceptionValidateView,
)


urlpatterns = [
    path(
        "receipts/",
        ReceptionListCreateView.as_view(),
        name="receipt-list-create",
    ),
    path(
        "receipts/<int:receipt_id>/",
        ReceptionDetailView.as_view(),
        name="receipt-detail",
    ),
    path(
        "receipts/<int:receipt_id>/document/",
        ReceptionDocumentView.as_view(),
        name="receipt-document",
    ),
    path(
        "receipts/<int:receipt_id>/validate/",
        ReceptionValidateView.as_view(),
        name="receipt-validate",
    ),
    path(
        "receipts/<int:receipt_id>/assign-location/",
        ReceptionLocationAssignmentView.as_view(),
        name="receipt-assign-location",
    ),
    path(
        "receipts/<int:receipt_id>/incidents/",
        ReceptionIncidentCreateView.as_view(),
        name="receipt-incident-create",
    ),
    path(
        "receipts/<int:receipt_id>/lots/",
        ReceptionLotsView.as_view(),
        name="receipt-lots",
    ),
    path(
        "catalogs/reception-options/",
        ReceptionOptionsView.as_view(),
        name="reception-options",
    ),
]
