# CANARD speed-camera source (prototype)

This repository now includes a **best-effort CANARD adapter prototype** in:

- `src/dataprep/canard_speed_cameras.py`

## What was investigated

For the MVP we attempted to use CANARD web data as the primary source of fixed speed-camera coordinates.

- A stable, officially documented public API endpoint for machine consumption was not confirmed in this repository workflow.
- The CANARD website can be unreachable from some environments (for example restricted CI/network sandboxes), so direct online fetch is not guaranteed.

Because of that, the implementation prefers resilience over brittle scraping.

## Implemented approach

`CanardSpeedCameraSource` tries endpoints in order:

1. Parse JSON/GeoJSON payloads
2. Parse CSV-like payloads
3. Parse basic HTML-embedded coordinate patterns (best effort)
4. If nothing reliable is obtained, fall back to local JSON dataset:
   - `src/dataprep/data/canard_speed_cameras_fallback.json`

If remote data is unavailable, the loader returns fallback points and a status message that explains the reason.

## Configuration

Optional environment variables:

- `FOREX_AGENT_CANARD_URLS` – comma-separated list of endpoint URLs
- `FOREX_AGENT_CANARD_FALLBACK_FILE` – override fallback file path

## Caveats (legal + technical)

- Website structure can change at any time; HTML parsing is intentionally minimal and non-critical.
- Verify CANARD publication terms for the specific dataset before production distribution.
- Fallback coordinates are demo-safe and keep the app/data pipeline buildable when remote CANARD data is unavailable.
- This change does **not** implement any Google Maps overlay or app modification mechanism.
