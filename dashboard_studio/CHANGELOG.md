# Changelog

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
