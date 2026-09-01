# HA Dashboard Studio

Generates Lovelace dashboard proposals from a design reference (image
upload) and your real entity/device/area inventory, so you can accept or
reject each view, section, card, color, and layout decision individually
before anything is written to Home Assistant.

This is Milestone 1: the App skeleton, the connection to Home Assistant's
WebSocket API, and a searchable, filterable snapshot of your entity
registry. Design analysis, dashboard generation, and writing a dashboard
into Home Assistant come in later milestones.

## Installation

1. In Home Assistant, go to **Settings → Apps → App Store**, add this
   repository, then install "HA Dashboard Studio".
2. Start the app. No configuration is required for Milestone 1 — the
   Anthropic API key and model become relevant starting in Milestone 2.
3. Open the app via the **Dashboard Studio** panel in the sidebar.

## Configuration

| Option | Description |
| --- | --- |
| `log_level` | Verbosity of the app's log output (`debug`/`info`/`warning`/`error`). |
| `anthropic_api_key` | Your Anthropic API key. Used server-side only, starting in Milestone 2. Never exposed to the frontend or logged. |
| `anthropic_model` | The Anthropic model used for design analysis and dashboard generation (default: `claude-sonnet-5`). Not used yet in Milestone 1. |
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
  Home Assistant instance except the design-analysis and dashboard-
  generation calls to the Anthropic API (from Milestone 2 onward).

## Support

Please open an issue on the
[GitHub repository](https://github.com/harmonisierend/Dashboard-Builder) if
you run into problems.
