from django.conf import settings
from django.core.management import call_command
from django.http import HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET


@csrf_exempt
@require_GET
def complete_past_bookings_endpoint(request):
    provided_secret = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()

    if not settings.CRON_SECRET or provided_secret != settings.CRON_SECRET:
        return HttpResponseForbidden("Forbidden")

    call_command("complete_past_bookings")
    return JsonResponse({"status": "ok"})