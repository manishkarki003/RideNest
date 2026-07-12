# RideNest Vehicle Rental System

Portfolio-quality Django vehicle rental platform, built in phases.

## Phase 1 roadmap and architecture

1. Foundation: Django project, custom user model, authentication, shared layout, static/media support.
2. Vehicles: owner listings, multi-image uploads, moderation, search and Leaflet locations.
3. Bookings: availability calendar, conflict-safe booking workflow, rental price snapshots.
4. Payments: Khalti gateway adapter and secure demo-payment fallback.
5. Trust and operations: reviews, notifications, dashboards, SEO and deployment hardening.

### Data model plan

`User` owns `Vehicle`; `Vehicle` has many `VehicleImage` records and `Booking` records. A `Booking` belongs to a member and has one `Payment`; eligible completed bookings can have one `Review`. `Notification` belongs to a user. Future foreign keys use server-side ownership checks and price snapshots to prevent IDOR and price manipulation.

### Folder structure

- `config/`: project configuration, URLs, ASGI/WSGI.
- `accounts/`: custom user model, registration, login and profile features.
- `core/`: shared public pages and reusable site concerns.
- `vehicles/`, `bookings/`, `payments/`, `reviews/`, `notifications/`, `dashboard/`: separate bounded feature apps.
- `templates/`: global Django templates; `static/`: custom CSS and future JavaScript; `media/`: local user uploads (not committed).

## Local setup

```powershell
Copy-Item .env.example .env
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

The project starts with SQLite. Keep `.env` private and use `.env.example` as the documented configuration template.

### Environment variables

- `DJANGO_SECRET_KEY`: secret Django signing key. A development-only fallback exists; always set this in production.
- `DJANGO_DEBUG`: `True` for local development and `False` in production.
- `DJANGO_ALLOWED_HOSTS`: comma-separated permitted host names.
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`: set `POSTGRES_DB` to switch from SQLite to PostgreSQL.

For a production deployment, provide a strong `DJANGO_SECRET_KEY`, set `DJANGO_DEBUG=False`, configure `DJANGO_ALLOWED_HOSTS`, and serve collected static files from `STATIC_ROOT`.
