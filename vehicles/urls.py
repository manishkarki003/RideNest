from django.urls import path
from .views import VehicleCreateView, VehicleDeleteView, VehicleDetailView, MyVehiclesView, VehicleSubmitView, VehicleUpdateView

app_name = "vehicles"
urlpatterns = [
    path("my/", MyVehiclesView.as_view(), name="mine"),
    path("add/", VehicleCreateView.as_view(), name="add"),
    path("<slug:slug>/", VehicleDetailView.as_view(), name="detail"),
    path("<slug:slug>/edit/", VehicleUpdateView.as_view(), name="edit"),
    path("<slug:slug>/delete/", VehicleDeleteView.as_view(), name="delete"),
    path("<slug:slug>/submit/", VehicleSubmitView.as_view(), name="submit"),
]
