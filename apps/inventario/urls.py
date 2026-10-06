from django.urls import path

from .views import (
    ExpirationAlertView,
    InventoryOptionsView,
    MovementConfirmView,
    MovementListCreateView,
    OccupancyView,
    RepackingView,
    StockListView,
)


urlpatterns = [
    path("inventory/stocks/", StockListView.as_view(), name="inventory-stocks"),
    path("inventory/occupancy/", OccupancyView.as_view(), name="inventory-occupancy"),
    path(
        "inventory/expiration-alerts/",
        ExpirationAlertView.as_view(),
        name="inventory-expiration-alerts",
    ),
    path(
        "catalogs/inventory-options/",
        InventoryOptionsView.as_view(),
        name="inventory-options",
    ),
    path(
        "inventory/movements/",
        MovementListCreateView.as_view(),
        name="inventory-movements",
    ),
    path(
        "inventory/movements/<int:movement_id>/confirm/",
        MovementConfirmView.as_view(),
        name="inventory-movement-confirm",
    ),
    path(
        "inventory/repacking/",
        RepackingView.as_view(),
        name="inventory-repacking",
    ),
]
