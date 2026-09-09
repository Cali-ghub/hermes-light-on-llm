# Changelog

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
