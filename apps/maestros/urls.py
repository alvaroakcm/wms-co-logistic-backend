from django.urls import path

from .views import (
    AlmacenListCreateView,
    ClienteDetailView,
    ClienteListCreateView,
    LocationOptionsView,
    MasterDataImportView,
    ProductOptionsView,
    ProductoDetailView,
    ProductoConversionCalculationView,
    ProductoListCreateView,
    UbicacionDetailView,
    UbicacionListCreateView,
    ZonaListCreateView,
)


urlpatterns = [
    path("clients/", ClienteListCreateView.as_view(), name="client-list-create"),
    path(
        "clients/<int:client_id>/",
        ClienteDetailView.as_view(),
        name="client-detail",
    ),
    path(
        "products/", ProductoListCreateView.as_view(), name="product-list-create"
    ),
    path(
        "products/<int:product_id>/",
        ProductoDetailView.as_view(),
        name="product-detail",
    ),
    path(
        "products/<int:product_id>/calculate-boxes/",
        ProductoConversionCalculationView.as_view(),
        name="product-calculate-boxes",
    ),
    path(
        "catalogs/product-options/",
        ProductOptionsView.as_view(),
        name="product-options",
    ),
    path(
        "warehouses/", AlmacenListCreateView.as_view(), name="warehouse-list-create"
    ),
    path("zones/", ZonaListCreateView.as_view(), name="zone-list-create"),
    path(
        "locations/", UbicacionListCreateView.as_view(), name="location-list-create"
    ),
    path(
        "locations/<int:location_id>/",
        UbicacionDetailView.as_view(),
        name="location-detail",
    ),
    path(
        "catalogs/location-options/",
        LocationOptionsView.as_view(),
        name="location-options",
    ),
    path(
        "imports/master-data/",
        MasterDataImportView.as_view(),
        name="master-data-import",
    ),
]
