# Inventory App (Django)

Simple inventory management app built with Django. Items can be listed, created, edited, searched, and (optionally) mapped by location. The code is structured around a single Django app named `app` inside a Django project named `inventory`.

## Table of contents

* [Overview](#overview)
* [Features](#features)
* [Tech stack](#tech-stack)
* [Project layout](#project-layout)
* [Data model](#data-model)
* [Getting started](#getting-started)
* [Environment variables (optional)](#environment-variables-optional)
* [Useful commands](#useful-commands)
* [Seed demo data](#seed-demo-data)
* [Main routes](#main-routes)
* [Templates and static files](#templates-and-static-files)
* [Testing](#testing)
* [Troubleshooting](#troubleshooting)
* [Roadmap](#roadmap)
* [License](#license)

## Overview

This project manages an item inventory with optional geolocation (lat/lng) so entries can be shown on a map. Items are owned by the logged-in user. There is support code for notifications, history, and custom context processors if needed by templates.

## Features

* Authenticated UI; data scoped to the current user (owner)
* CRUD for items: name, SKU, quantity, city, building, address, optional coordinates
* Search and filters (q, city, building) in list/map views
* Optional: notifications list with read/unread and type filtering
* Optional: history log page for key actions

> Some pages/features may be disabled if their URL is not wired up. See [Main routes](#main-routes).

## Tech stack

* **Backend:** Django 4+
* **DB:** SQLite locally (any Django-supported DB works)
* **UI:** Django Templates + vanilla CSS
* **Map provider (optional):** Google Maps (static/dynamic) or Leaflet + OpenStreetMap

## Project layout

Matches the current repository structure:

```
inventory/                     # project root
├─ app/
│  ├─ management/             # custom management commands (e.g. seed)
│  ├─ migrations/
│  ├─ static/                 # app-level static
│  ├─ templates/              # app-level templates (override-able)
│  ├─ __init__.py
│  ├─ admin.py
│  ├─ apps.py
│  ├─ context_processors.py   # extra context for templates
│  ├─ forms.py
│  ├─ models.py
│  ├─ signals.py
│  ├─ tests.py
│  ├─ urls.py                 # app URLs
│  ├─ utils.py
│  └─ views.py
├─ inventory/
│  ├─ __init__.py
│  ├─ settings.py
│  ├─ urls.py                 # project URLs (includes app.urls)
│  └─ wsgi.py
├─ templates/                 # project-level templates
├─ manage.py
├─ requirements.txt
├─ db.sqlite3                 # local dev database
├─ .venv/ or venv/            # local virtual environment (ignored in VCS)
```

## Data model

### Item (typical fields)

* `name`: `CharField`
* `sku`: `CharField`
* `quantity`: `IntegerField`
* `city`: `CharField`
* `building`: `CharField`
* `address`: `CharField`
* `lat`, `lng`: `FloatField` (optional)
* `owner`: `ForeignKey` → `User`
* `created_at`: `DateTimeField`

### Notification (optional)

* `user`: `ForeignKey` → `User`
* `title`, `message`: `CharField`/`TextField`
* `type`: `CharField` (INFO/WARNING/ERROR)
* `is_read`: `BooleanField`
* `created_at`: `DateTimeField`

> Field names can vary slightly in your code; the above reflects the intent.

## Getting started

1. **Python**: Install Python 3.11+.

2. **Create and activate a venv**

```bash
python3.11 -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows
# .venv\Scripts\Activate.ps1
```

3. **Install dependencies**

```bash
pip install -r requirements.txt
```

4. **Migrate and create a superuser**

```bash
python manage.py migrate
python manage.py createsuperuser
```

5. **Run the dev server**

```bash
python manage.py runserver
```

Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/).

## Environment variables (optional)

Create an `.env` if you want to keep secrets/configs out of settings:

```
DEBUG=true
SECRET_KEY=change_me
ALLOWED_HOSTS=127.0.0.1,localhost

# Map provider configuration (pick one)
MAPS_PROVIDER=leaflet         # or "google"
GOOGLE_MAPS_API_KEY=...       # required if MAPS_PROVIDER=google
```

Wire this up with `python-dotenv` or your preferred approach.

## Useful commands

```bash
# make/apply migrations
python manage.py makemigrations
python manage.py migrate

# open Django shell
python manage.py shell

# run tests
python manage.py test
```

## Seed demo data

Quick one-off via shell:

```bash
python manage.py shell <<'PY'
from django.contrib.auth import get_user_model
from app.models import Item
U = get_user_model()

USERNAME = "admin"  # adjust as needed
user = U.objects.filter(username=USERNAME).first() or U.objects.create_user(USERNAME, password="admin123")

rows = [
    dict(name="iPhone 17",  sku="9089", quantity=8,  city="Arad",        building="Warehouse A", address="Str. Victoriei 10",  lat=46.1667, lng=21.3167),
    dict(name="MacBook Pro",sku="5012", quantity=3,  city="Timisoara",   building="Warehouse B", address="Str. Daliei 2",      lat=45.7489, lng=21.2087),
    dict(name="Router",     sku="1001", quantity=15, city="Cluj-Napoca", building="Warehouse C", address="Str. Eroilor 5",     lat=46.7712, lng=23.6236),
]

for d in rows:
    Item.objects.get_or_create(owner=user, sku=d["sku"], defaults=d)
print("Seed OK")
PY
```

Prefer a reusable command? Add `app/management/commands/seed_inventory.py` and run:

```bash
python manage.py seed_inventory
```

## Main routes

* `/` or `/items/` – item list with search/pagination
* `/items/new` – create item
* `/items/<id>/edit` – edit item
* `/map/` – map + filters (`q`, `city`, `building`)
* `/notifications/` – list notifications (`?status=unread|read`, `?type=<type>`)
* `/history/` – history log

> If you hit a 404 (e.g., `/history/`), confirm the view is implemented and that the route is included in `app/urls.py` and `inventory/urls.py`.

## Templates and static files

* App templates live in `app/templates/`, while project-wide overrides can go in the root `templates/` folder. Django searches both when properly configured in `TEMPLATES.DIRS` and `APP_DIRS=True`.
* Place CSS/JS/images in `app/static/` (or a project `static/` directory if you add one) and ensure `STATIC_URL`/`STATICFILES_DIRS`/`STATIC_ROOT` are configured for your environment.

## Testing

```bash
python manage.py test
```

## Troubleshooting

* **`zsh: command not found: python`** → use `python3` or activate your venv: `source .venv/bin/activate`.
* **Nothing shows on the map** → ensure items have `lat`/`lng` and your map provider is configured.
* **City/building choices don’t load** → check how `forms.py` populates choices and that data exists in the backing tables (e.g., a `CityLocation` model if used).
* **404 on pages** → verify URL patterns are wired in both `app/urls.py` and `inventory/urls.py` and the template exists.

## Roadmap

* CSV/Excel export and CSV import with validation
* Roles/permissions (viewer/editor)
* Email/webhook notifications
* CI with unit/integration tests

## License

MIT (or your choice).
