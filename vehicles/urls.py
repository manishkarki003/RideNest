from django.urls import path
from .views import (
    MarketplaceView, PublicVehicleDetailView, VehicleCreateView, VehicleDeleteView,
    VehicleDetailView, MyVehiclesView, VehicleSubmitView, VehicleUpdateView,
)

app_name = "vehicles"
urlpatterns = [
    path("", MarketplaceView.as_view(), name="marketplace"),
    path("search/", MarketplaceView.as_view(), {"is_search_results": True}, name="search"),
    path("my/", MyVehiclesView.as_view(), name="mine"),
    path("add/", VehicleCreateView.as_view(), name="add"),
    path("my/<slug:slug>/", VehicleDetailView.as_view(), name="detail"),
    path("my/<slug:slug>/edit/", VehicleUpdateView.as_view(), name="edit"),
    path("my/<slug:slug>/delete/", VehicleDeleteView.as_view(), name="delete"),
    path("my/<slug:slug>/submit/", VehicleSubmitView.as_view(), name="submit"),
    path("<slug:slug>/", PublicVehicleDetailView.as_view(), name="public_detail"),
]
