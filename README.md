# HA Dashboard Studio

A Home Assistant App that generates Lovelace dashboard proposals from a
design reference (image upload, later also a URL screenshot) and your real
entity/device/area inventory. You accept or reject each view, section,
card, color, and layout decision individually, and the result is written
as a new dashboard in Home Assistant — responsive for mobile, tablet,
desktop, and wall-panel devices.

The app runs entirely inside your own Home Assistant instance (Ingress-only,
no exposed port) and stores everything locally under `/data`. The only
external call is to the Anthropic API for design analysis and dashboard
generation, configured with your own API key.

## Status: Milestone 2

This repository currently implements **Milestones 1–2**: the app skeleton,
Ingress panel, a connection to Home Assistant's WebSocket API, a
searchable/filterable snapshot of your entity registry, and design-token
analysis from an uploaded reference image (color palette, typography, form,
density, card-style classification) with an editor, savable presets, and
HA-theme export. See [`dashboard_studio/CHANGELOG.md`](dashboard_studio/CHANGELOG.md)
for what's implemented and [`dashboard_studio/DOCS.md`](dashboard_studio/DOCS.md)
for user-facing documentation.

Dashboard generation, entity curation, live preview, and writing dashboards
back into Home Assistant are later milestones (M3–M7).

## Repository layout

```
repository.yaml          HA App-repository manifest
dashboard_studio/         the App itself
├── config.yaml           App manifest (Ingress, options, arch)
├── Dockerfile            multi-stage build: frontend -> Python runtime
├── DOCS.md               user-facing app documentation
├── CHANGELOG.md          per-milestone changelog
├── backend/              FastAPI backend (Python 3.12)
└── frontend/             Vite + React + TypeScript + Tailwind UI
```

## Local development

The app is designed to run inside a Home Assistant App container (with
`SUPERVISOR_TOKEN` injected automatically), but both halves can be run and
tested standalone.

### Backend

```sh
cd dashboard_studio/backend
python3.12 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"

# Outside the Supervisor sandbox, SUPERVISOR_TOKEN isn't set, so configure
# a long-lived access token against a real (or test) HA instance instead:
export DASHBOARD_STUDIO_DATA_DIR=./.data
export DASHBOARD_STUDIO_LONG_LIVED_TOKEN=<a long-lived access token>
export DASHBOARD_STUDIO_HA_URL=http://homeassistant.local:8123

# To exercise the Design page's image analysis locally:
export DASHBOARD_STUDIO_ANTHROPIC_API_KEY=<your Anthropic API key>

cd src && python -m uvicorn dashboard_studio.main:app --reload --port 8099
```

Run the tests and checks:

```sh
cd dashboard_studio/backend
pytest -v
ruff check src tests
mypy src
```

Database migrations (SQLite, under `$DASHBOARD_STUDIO_DATA_DIR`):

```sh
alembic upgrade head
```

### Frontend

```sh
cd dashboard_studio/frontend
npm install
npm run dev   # dev server with hot reload
```

Run the tests and checks:

```sh
cd dashboard_studio/frontend
npm test
npm run lint
npm run typecheck
npm run build
```

## Installing the App in Home Assistant

1. In Home Assistant, go to **Settings → Apps → App Store**, add this
   repository (or clone it locally and add it as a local app repository),
   then install "HA Dashboard Studio".
2. Start the app and open it via the **Dashboard Studio** panel in the
   sidebar.

Set `anthropic_api_key` in the app's options to use the Design page's image
analysis; everything else works without configuration. See
[`dashboard_studio/DOCS.md`](dashboard_studio/DOCS.md) for the full option
reference.

## CI

- `.github/workflows/lint.yml` — ruff/mypy (backend), eslint/tsc
  (frontend), a `config.yaml` YAML-validity check.
- `.github/workflows/test.yml` — pytest (backend), vitest (frontend).
- `.github/workflows/build.yml` — multi-arch (`amd64`, `aarch64`) Docker
  image build via buildx, to prove the App builds for both target
  architectures. Real install/runtime verification for Milestone 1 has
  been done on `amd64` only; `aarch64` hardware wasn't available yet.
