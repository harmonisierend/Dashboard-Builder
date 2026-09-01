# Changelog

## 0.4.0 - Milestone 4

- Per-entity curation: dashboard generation is now a two-step flow.
  "Struktur vorschlagen" proposes a view structure and resolves each
  proposed view's candidate entities (the existing phase-1 call), without
  generating any cards yet. You then review each proposed view and every
  candidate entity individually, drop whichever views or entities you
  don't want, and only then click "Dashboard generieren" to spend an LLM
  call on cards for what you actually kept.
- Curation is opt-out, not opt-in: every proposed view and every candidate
  entity starts checked, so clicking straight through reproduces
  Milestone 3's one-shot behavior with zero extra clicks.
- Per-view "Alle auswählen" / "Keine auswählen" shortcuts for quickly
  selecting or clearing every candidate in one view.
- The hard entity-ID validation guarantee from Milestone 3 is unconditional
  and independent of curation: the final `/generate` call re-derives the
  valid entity set from the live registry regardless of what was curated,
  so a generated dashboard still can never reference a nonexistent entity.
- `POST /api/dashboard/generate` now takes curated view/entity selections
  instead of a scope+strategy pair (that moved to the new
  `POST /api/dashboard/propose-structure`); this is a breaking API change,
  not backward compatible with 0.3.0's request shape.

## 0.3.0 - Milestone 3

- Dashboard generation: pick one or more Areas/Floors as scope, choose a
  view-structuring strategy ("Nach Bereichen" / "Nach Domains" /
  "Automatisch"), and generate a proposed Lovelace dashboard from your real
  entity inventory via the Anthropic API — nothing is written to Home
  Assistant yet.
- Generation runs in two phases: a cheap structure call proposes the set of
  views from a scope summary, then each view's cards are generated in
  parallel from the actual candidate entities for that view.
- **Hard entity-ID validation guarantee**: every entity ID and custom card
  type in the generated result is cross-checked against your real registry
  snapshot before you ever see it. Anything that doesn't exist is stripped
  (an invalid single-entity card is dropped entirely; an invalid ID inside
  an entities list is removed from that list; an unavailable custom card
  type falls back to its native equivalent) — a generated dashboard can
  never reference an entity that doesn't exist. A validation report shows
  exactly what, if anything, was removed and why.
- Native cards first: tile, heading, entities, thermostat, history-graph,
  weather-forecast, light, media-control. Custom card types (currently
  Mushroom and Bubble Card) are only used when actually detected as
  installed via your Lovelace resources — never invented.
- Optionally applies a saved design-token preset (from Milestone 2) as a
  style hint influencing density and card-style choices during generation.
- A per-view generation failure doesn't void the whole result — it's
  reported as a note and the rest of the dashboard is still returned.
- Review the proposed views, sections, and cards, then download the result
  as a ready-to-paste `dashboard.yaml` for Home Assistant's Lovelace
  YAML-mode editor.
- Logs and displays combined Anthropic token usage and an estimated cost
  across all calls for one generation (structure call + all view calls).

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
