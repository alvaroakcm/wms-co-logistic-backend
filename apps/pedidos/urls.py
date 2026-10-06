from django.urls import path

from .views import (
    OrderDetailView,
    OrderDocumentView,
    OrderCancelView,
    OrderDispatchView,
    OrderListCreateView,
    OrderOptionsView,
    OrderPreparationView,
    OrderStockValidationView,
    DispatchHistoryView,
    DispatchIncidentView,
)


urlpatterns = [
    path("orders/", OrderListCreateView.as_view(), name="order-list-create"),
    path("orders/<int:order_id>/", OrderDetailView.as_view(), name="order-detail"),
    path(
        "orders/<int:order_id>/document/",
        OrderDocumentView.as_view(),
        name="order-document",
    ),
    path(
        "orders/<int:order_id>/validate-stock/",
        OrderStockValidationView.as_view(),
        name="order-validate-stock",
    ),
    path(
        "orders/<int:order_id>/prepare/",
        OrderPreparationView.as_view(),
        name="order-prepare",
    ),
    path(
        "orders/<int:order_id>/cancel/",
        OrderCancelView.as_view(),
        name="order-cancel",
    ),
    path(
        "orders/<int:order_id>/dispatch/",
        OrderDispatchView.as_view(),
        name="order-dispatch",
    ),
    path(
        "orders/<int:order_id>/dispatch/incidents/",
        DispatchIncidentView.as_view(),
        name="dispatch-incident",
    ),
    path(
        "dispatches/history/",
        DispatchHistoryView.as_view(),
        name="dispatch-history",
    ),
    path(
        "catalogs/order-options/", OrderOptionsView.as_view(), name="order-options"
    ),
]
