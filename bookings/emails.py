"""Transactional email service for the bookings app.

Kept fully separate from views/signals: this module owns HTML rendering
and the Resend API call. It never raises — any failure is logged so the
booking confirmation workflow is never affected by email delivery issues.
"""
from __future__ import annotations

import logging

import resend
from django.conf import settings
from django.urls import reverse

logger = logging.getLogger(__name__)


def _resend_client_ready() -> bool:
    api_key = getattr(settings, "RESEND_API_KEY", None)
    if not api_key:
        logger.error(
            "RESEND_API_KEY is not configured; cannot send booking confirmation email."
        )
        return False
    resend.api_key = api_key
    return True


def _owner_display_name(owner) -> str:
    """
    NOTE: accounts.User model was not provided to me, so this is written
    defensively rather than assuming a field name. Verify against your
    actual User model and simplify once confirmed.
    """
    get_full_name = getattr(owner, "get_full_name", None)
    if callable(get_full_name):
        name = get_full_name()
        if name:
            return name
    first = getattr(owner, "first_name", "") or ""
    last = getattr(owner, "last_name", "") or ""
    if (first or last):
        return f"{first} {last}".strip()
    return getattr(owner, "username", "The vehicle owner")


def _owner_contact(owner) -> str:
    """
    NOTE: same caveat as above — I don't know if you have a phone_number
    field. Update the attribute names below once you confirm your User
    model's actual field name.
    """
    for attr in ("phone_number", "phone", "email"):
        value = getattr(owner, attr, None)
        if value:
            return str(value)
    return "Available via RideNest support"


def _booking_detail_url(booking) -> str:
    site_url = getattr(settings, "SITE_URL", "http://127.0.0.1:8000").rstrip("/")
    path = reverse(
        "bookings:booking_detail",
        kwargs={"booking_reference": booking.booking_reference},
    )
    return f"{site_url}{path}"


def _vehicle_image_url(vehicle) -> str | None:
    image = vehicle.primary_image
    if image and getattr(image, "image", None):
        try:
            return image.image.url
        except ValueError:
            return None
    return None


def send_booking_confirmation_email(booking) -> None:
    """
    Sends a 'Booking Confirmed' email to the renter via Resend.

    Never raises. Any failure (missing API key, network error, bad
    payload, etc.) is logged and swallowed so the caller — the booking
    confirmation signal — is never affected.
    """
    try:
        renter_email = getattr(booking.renter, "email", None)
        if not renter_email:
            logger.warning(
                "Booking %s renter has no email address; skipping confirmation email.",
                booking.booking_reference,
            )
            return

        if not _resend_client_ready():
            return

        resend.Emails.send({
            "from": settings.DEFAULT_FROM_EMAIL,
            "to": [renter_email],
            "subject": f"Booking Confirmed — {booking.vehicle.name} ({booking.short_reference})",
            "html": _render_confirmation_html(booking),
        })

        logger.info(
            "Booking confirmation email sent for booking %s to %s.",
            booking.booking_reference,
            renter_email,
        )
    except Exception:
        logger.exception(
            "Failed to send booking confirmation email for booking %s.",
            booking.booking_reference,
        )


def _render_confirmation_html(booking) -> str:
    vehicle = booking.vehicle
    owner = booking.owner
    image_url = _vehicle_image_url(vehicle)
    booking_url = _booking_detail_url(booking)

    image_block = (
        f'<img src="{image_url}" alt="{vehicle.name}" width="100%" '
        'style="display:block;width:100%;max-height:280px;object-fit:cover;'
        'border-radius:10px;margin:0 0 28px 0;" />'
        if image_url else ""
    )

    return f"""\
<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background-color:#f4f5f7;
             font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="background-color:#f4f5f7;padding:32px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
               style="max-width:560px;background-color:#ffffff;border-radius:12px;
                      overflow:hidden;box-shadow:0 2px 10px rgba(0,0,0,0.06);">

          <!-- Header -->
          <tr>
            <td style="background-color:#111827;padding:24px 32px;">
              <span style="font-size:22px;font-weight:700;color:#ffffff;letter-spacing:-0.5px;">
                🚗 RideNest
              </span>
            </td>
          </tr>

          <!-- Success banner -->
          <tr>
            <td style="padding:32px 32px 0 32px;text-align:center;">
              <div style="width:56px;height:56px;line-height:56px;border-radius:50%;
                          background-color:#dcfce7;color:#16a34a;font-size:28px;
                          margin:0 auto 16px auto;">✓</div>
              <h1 style="margin:0 0 8px 0;font-size:22px;color:#111827;">Booking Confirmed</h1>
              <p style="margin:0 0 24px 0;color:#6b7280;font-size:14px;">
                Your ride is booked and ready to go.
              </p>
            </td>
          </tr>

          <!-- Vehicle image -->
          <tr>
            <td style="padding:0 32px;">
              {image_block}
            </td>
          </tr>

          <!-- Booking details card -->
          <tr>
            <td style="padding:0 32px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                     style="background-color:#f9fafb;border-radius:10px;padding:20px;">
                <tr>
                  <td style="padding:6px 0;font-size:13px;color:#6b7280;">Booking reference</td>
                  <td style="padding:6px 0;font-size:13px;color:#111827;font-weight:600;text-align:right;">
                    {booking.short_reference}
                  </td>
                </tr>
                <tr>
                  <td style="padding:6px 0;font-size:13px;color:#6b7280;">Vehicle</td>
                  <td style="padding:6px 0;font-size:13px;color:#111827;font-weight:600;text-align:right;">
                    {vehicle.name}
                  </td>
                </tr>
                <tr>
                  <td style="padding:6px 0;font-size:13px;color:#6b7280;">Pickup date</td>
                  <td style="padding:6px 0;font-size:13px;color:#111827;font-weight:600;text-align:right;">
                    {booking.pickup_date:%B %d, %Y}
                  </td>
                </tr>
                <tr>
                  <td style="padding:6px 0;font-size:13px;color:#6b7280;">Return date</td>
                  <td style="padding:6px 0;font-size:13px;color:#111827;font-weight:600;text-align:right;">
                    {booking.return_date:%B %d, %Y}
                  </td>
                </tr>
                <tr>
                  <td style="padding:6px 0;font-size:13px;color:#6b7280;">Pickup location</td>
                  <td style="padding:6px 0;font-size:13px;color:#111827;font-weight:600;text-align:right;">
                    {vehicle.pickup_address}
                  </td>
                </tr>
                <tr>
                  <td style="padding:10px 0 0 0;font-size:13px;color:#6b7280;border-top:1px solid #e5e7eb;">
                    Total amount
                  </td>
                  <td style="padding:10px 0 0 0;font-size:15px;color:#111827;font-weight:700;
                             text-align:right;border-top:1px solid #e5e7eb;">
                    Rs. {booking.total_amount}
                  </td>
                </tr>
                <tr>
                  <td style="padding:6px 0;font-size:13px;color:#6b7280;">Status</td>
                  <td style="padding:6px 0;text-align:right;">
                    <span style="background-color:#dcfce7;color:#16a34a;font-size:12px;
                                 font-weight:600;padding:4px 10px;border-radius:999px;">
                      {booking.get_booking_status_display()}
                    </span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Owner info -->
          <tr>
            <td style="padding:20px 32px 0 32px;">
              <p style="margin:0 0 4px 0;font-size:13px;color:#6b7280;">Vehicle owner</p>
              <p style="margin:0;font-size:14px;color:#111827;font-weight:600;">
                {_owner_display_name(owner)}
              </p>
              <p style="margin:2px 0 0 0;font-size:13px;color:#6b7280;">
                {_owner_contact(owner)}
              </p>
            </td>
          </tr>

          <!-- CTA -->
          <tr>
            <td style="padding:28px 32px;text-align:center;">
              <a href="{booking_url}"
                 style="display:inline-block;background-color:#111827;color:#ffffff;
                        font-size:14px;font-weight:600;text-decoration:none;
                        padding:14px 32px;border-radius:8px;">
                View Booking
              </a>
            </td>
          </tr>

          <!-- Support -->
          <tr>
            <td style="padding:0 32px 24px 32px;text-align:center;">
              <p style="margin:0;font-size:12px;color:#9ca3af;">
                Need help? Contact RideNest support at
                <a href="mailto:support@ridenest.com" style="color:#6366f1;">support@ridenest.com</a>
              </p>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background-color:#f9fafb;padding:20px 32px;text-align:center;
                       border-top:1px solid #e5e7eb;">
              <p style="margin:0;font-size:11px;color:#9ca3af;">
                &copy; {booking.created_at.year} RideNest. All rights reserved.<br />
                This is an automated message — please do not reply directly to this email.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""