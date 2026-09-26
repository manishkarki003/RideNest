from django.db.models import Avg, Count
from django.shortcuts import render

from reviews.models import Review


def home(request):
    review_totals = Review.objects.aggregate(average=Avg("rating"), total=Count("id"))
    context = {
        "average_rating": round(review_totals["average"], 1) if review_totals["average"] is not None else None,
        "review_count": review_totals["total"],
    }
    return render(request, "core/home.html", context)