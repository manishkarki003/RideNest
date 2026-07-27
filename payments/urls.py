from django.urls import path

from payments import views

app_name = "payments"

urlpatterns = [
    path("<uuid:booking_id>/initiate/", views.PaymentInitiateView.as_view(), name="initiate"),
    path("<uuid:pk>/status/", views.PaymentStatusView.as_view(), name="status"),
]