# Changelog

## 0.2.0 - Milestone 2

- Design-reference image upload (PNG/JPEG/WebP, MIME- and size-validated),
  stored under `/data/uploads`.
- Design analysis via the Anthropic API: a vision call turns the uploaded
  image into a strict, schema-validated design-token set (color palette
  with light/dark variants, typography, form, density, card-style
  classification). Token usage and an estimated cost are logged and
  returned per call; no hard budget cap.
- Token editor UI: color pickers, sliders, and text/select inputs for every
  token, grouped by category, with a mandatory notice that only abstract
  design characteristics are derived from the reference — never a 1:1
  reproduction of its layout or copyrighted content.
- Token presets: save, list, load, and delete reusable design-token sets
  (SQLite-backed, `token_schema_version`-tagged for future schema changes).
- Export the current token set as an HA `themes.yaml`-compatible theme
  (light/dark `modes:`), with a note that a theme reload is needed in HA to
  pick it up.
- Database migrations now run automatically on app startup (no interactive
  shell required inside the App container).

## 0.1.0 - Milestone 1

- Initial App skeleton: Docker packaging, Ingress panel, multi-arch build
  (amd64, aarch64).
- Connection to Home Assistant's WebSocket API (Supervisor token in
  production, long-lived-token fallback for local development).
- Entity/device/area/floor/label registry snapshot, cached in memory and
  persisted to `/data`, with default include/exclude filtering
  (hidden/disabled entities excluded; config/diagnostic entities excluded
  by default but togglable; unavailable/unknown entities flagged, not
  dropped).
- Searchable, filterable, virtualized entity list in the UI (search by
  name/ID; filter by Area, Floor, Domain, Label), built to stay responsive
  at the full ~2300-entity scale of the target instance.
