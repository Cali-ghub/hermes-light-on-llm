# Changelog

## 2.1.0

- Add configurable local-time idle quiet hours, defaulting to 23:30–06:00.
- Turn the light off only for `IDLE` during quiet hours; thinking, cron, and approval states remain illuminated.
- Add a lightweight boundary watcher so an already-idle green light turns off at quiet-hours start and resumes normal idle behavior at its end.
- Apply the same idle quiet-hours rule to both dashboard API surfaces.

## 2.0.1

- Fix Hubitat Maker API URL construction so `access_token` is added with a query separator.
- Fix Hubitat cloud-thinking purple to use Hubitat's 0-100 hue scale.
- Avoid caching a light color as current unless the backend call succeeds.
- Add unit tests for state selection, Hubitat URL generation, and failed-call cache behavior.
- Add GitHub Actions CI for tests, Python compilation, JSON manifest validation, and simple privacy checks.
- Add MIT license.
- Clarify README support matrix: Hue direct is recommended; Hubitat is legacy/best-effort; Govee via Hubitat is driver-dependent; Desktop companion is Hue-only.

## 2.0.0

- Added Hermes Desktop plugin support.
- Added model-aware thinking colors for local, cloud, and cron runs.
- Externalized runtime configuration through environment variables.
- Removed local/private defaults from publishable source.
