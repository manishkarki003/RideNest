"""Views for creating a review on a completed booking."""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from bookings.models import Booking

from .forms import ReviewForm


@login_required
def create_review(request, booking_reference):
    booking = get_object_or_404(Booking, booking_reference=booking_reference, renter=request.user)

    if booking.booking_status != Booking.Status.COMPLETED:
        messages.error(request, "You can only review a completed booking.")
        return redirect("bookings:booking_detail", booking_reference=booking.booking_reference)

    if hasattr(booking, "review"):
        messages.info(request, "You've already reviewed this booking.")
        return redirect("bookings:booking_detail", booking_reference=booking.booking_reference)

    if request.method == "POST":
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.booking = booking
            try:
                review.save()
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(request, "Thanks for your review!")
                return redirect("bookings:booking_detail", booking_reference=booking.booking_reference)
    else:
        form = ReviewForm()

    return render(request, "reviews/review_form.html", {"form": form, "booking": booking})