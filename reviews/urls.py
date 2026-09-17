from django.urls import path

from . import views

app_name = "reviews"

urlpatterns = [
    path("bookings/<uuid:booking_reference>/review/", views.create_review, name="create_review"),
]