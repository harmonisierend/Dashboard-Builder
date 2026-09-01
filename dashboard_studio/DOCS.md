# HA Dashboard Studio

Generates Lovelace dashboard proposals from a design reference (image
upload) and your real entity/device/area inventory, so you can accept or
reject each view, section, card, color, and layout decision individually
before anything is written to Home Assistant.

This is through Milestone 4: the App skeleton, the connection to Home
Assistant's WebSocket API, a searchable/filterable snapshot of your entity
registry, design-token analysis from an uploaded reference image, and
generating a downloadable dashboard proposal from your real entity
inventory with per-entity curation before anything is generated. Writing a
dashboard into Home Assistant and a live preview come in later milestones.

## Installation

1. In Home Assistant, go to **Settings → Apps → App Store**, add this
   repository, then install "HA Dashboard Studio".
2. To use the Design page, set `anthropic_api_key` in the app's options
   (see below). Everything else works without configuration.
3. Open the app via the **Dashboard Studio** panel in the sidebar.

## Configuration

| Option | Description |
| --- | --- |
| `log_level` | Verbosity of the app's log output (`debug`/`info`/`warning`/`error`). |
| `anthropic_api_key` | Your Anthropic API key, required to use the Design page's image analysis. Used server-side only. Never exposed to the frontend or logged. |
| `anthropic_model` | The Anthropic model used for design analysis (default: `claude-sonnet-5`). |
| `long_lived_token` | Only needed for local development outside the Supervisor sandbox. Leave empty in a normal installation — the Supervisor-provided token is used automatically. |

## What Milestone 1 does

- Connects to Home Assistant's WebSocket API using the Supervisor-provided
  token.
- Fetches and caches a snapshot of your entity, device, area, floor, and
  label registries, plus current states and installed Lovelace resources
  (so later milestones know which custom cards, like Mushroom or Bubble
  Card, are actually available).
- Shows the entity inventory in a searchable, filterable, virtualized list
  (search by name/ID; filter by Area, Floor, Domain, or Label) that stays
  responsive at the full ~2300-entity scale.
- Applies the default entity filtering rules: entities hidden or disabled
  in the registry are excluded; `config`/`diagnostic` entities are excluded
  by default but can be toggled back on; entities that are unavailable or
  in an unknown state are flagged, never silently dropped.

## What Milestone 2 does

- Lets you upload a design-reference image (PNG/JPEG/WebP, up to 6 MB) on
  the **Design** page.
- Sends it to the Anthropic API (your configured model, default
  `claude-sonnet-5`) to derive a design-token set: a color palette (with
  separate light and dark variants), typography, corner/border/shadow
  style, spacing density, and a card-style classification.
- **The reference is used only to derive abstract design characteristics —
  colors, spacing, density, style direction. It is never reproduced
  layout-for-layout, and no copyrighted content from it is copied.** This
  notice is also shown in the UI next to the upload area.
- Lets you review and adjust every token by hand (color pickers, sliders,
  text fields) before using it anywhere.
- Lets you save a token set as a named, reusable preset, and load or delete
  saved presets later.
- Lets you export the current token set as an HA-compatible `themes.yaml`
  snippet. Home Assistant needs a theme reload after you add it for the
  change to take effect.
- Logs the Anthropic token usage and an estimated cost for every analysis
  call (there's no hard spending cap — this is informational).

## What Milestone 3 does

- Adds a **Dashboard** page: pick one or more Areas and/or Floors as the
  generation scope, choose how views should be structured ("Nach
  Bereichen" / "Nach Domains" / "Automatisch"), optionally pick a saved
  design-token preset as a style hint, and generate a proposed dashboard.
- Generation is a two-phase Anthropic API call: first a cheap call proposes
  the set of views from a scope summary (never the full entity list), then
  each view's cards are generated from the actual candidate entities for
  that view, in parallel.
- **No generated dashboard can ever reference an entity that doesn't
  exist.** Every entity ID and custom card type in the result is
  cross-checked against your real registry snapshot before you see it:
  invalid single-entity cards are dropped, invalid IDs are stripped out of
  multi-entity cards, and unavailable custom card types fall back to their
  native equivalent. A validation report always shows exactly what was
  removed, if anything.
- Uses native Lovelace cards by default (tile, heading, entities,
  thermostat, history-graph, weather-forecast, light, media-control).
  Custom card types (currently Mushroom and Bubble Card) are only used when
  actually detected as installed via your Lovelace resources.
- If generating one view's cards fails, the rest of the dashboard is still
  returned, with a note explaining what was skipped and why.
- Review the proposed views/sections/cards, then download the result as a
  `dashboard.yaml` file that pastes directly into Home Assistant's Lovelace
  YAML-mode editor. **Nothing is written to Home Assistant automatically —
  that's a later milestone.**
- Logs and displays combined token usage and an estimated cost across every
  Anthropic call made for one generation.

## What Milestone 4 does

- Turns dashboard generation into a two-step flow instead of one click.
  **"Struktur vorschlagen"** runs only the cheap phase-1 call: it proposes
  the set of views and resolves each one's candidate entities from your
  scope, but generates no cards yet.
- You then see every proposed view and every one of its candidate entities
  as an individually checked checkbox — **everything starts selected**, so
  clicking straight through to **"Dashboard generieren"** reproduces
  Milestone 3's one-shot behavior with no extra effort. Uncheck an entity
  to leave it out, or uncheck a whole view to drop it, before spending an
  LLM call generating its cards. Per-view "Alle auswählen" / "Keine
  auswählen" shortcuts speed up bulk changes.
- Only after you click **"Dashboard generieren"** does phase 2 run — and
  only for the views/entities you actually kept, so nothing you excluded
  ever costs a card-generation call.
- The Milestone 3 hard entity-ID validation guarantee is unconditional:
  the final generation step re-derives the valid entity set from your live
  registry independently of what was curated, so no generated dashboard
  can reference a nonexistent entity, no matter what was selected.

## What this app does not do

- It never modifies an existing dashboard without your explicit
  confirmation, and always backs up the previous configuration first
  (starting Milestone 6).
- It never creates or edits automations, scripts, or helpers.
- It never renames entities in the registry.
- It never manages HACS installations — if a proposed card needs a
  HACS-installed component you don't have, it tells you and offers a
  native-card fallback instead.
- Nothing about your dashboard, entities, or design references leaves your
  Home Assistant instance except the design-analysis calls to the
  Anthropic API (and dashboard-generation calls, from Milestone 3 onward).

## Support

Please open an issue on the
[GitHub repository](https://github.com/harmonisierend/Dashboard-Builder) if
you run into problems.
