from django.urls import path
from .cron import complete_past_bookings_endpoint
from .views import BookingDetailView, BookingHistoryView, BookingHomeView, BookingManageView, BookingRequestView

app_name = "bookings"
urlpatterns = [
    path("", BookingHomeView.as_view(), name="index"),
    path("request/<slug:vehicle_slug>/", BookingRequestView.as_view(), name="request"),
    path("history/", BookingHistoryView.as_view(), name="history"),
    path("manage/", BookingManageView.as_view(), name="manage"),
    path("cron/complete-past-bookings/", complete_past_bookings_endpoint, name="cron_complete_past_bookings"),
    path("<uuid:booking_reference>/", BookingDetailView.as_view(), name="booking_detail"),
]