# light-on-llm

A visual status indicator for Hermes Agent that drives a smart light based on agent state.

This repo covers **two plugin surfaces**:

1. **Hermes plugin** for gateway / TUI / WebUI / cron runs
2. **Hermes Desktop plugin companion** for the desktop app surface

The current release shape is designed to be **publish-safe**:
- no real IPs in source
- no API keys in source
- no user-specific scene IDs in source
- configuration comes from environment variables only

## Capability Summary

| Capability | Status |
|---|---|
| Hermes plugin hooks (`pre_llm_call`, `post_llm_call`, approval hooks) | ✅ |
| Local vs cloud color distinction | ✅ |
| Cron-specific color | ✅ |
| Philips Hue direct light writes | ✅ recommended |
| Hubitat Maker API fallback | ⚠️ legacy / best-effort |
| Govee via Hubitat | ⚠️ driver-dependent |
| Desktop plugin support | ✅ Hue direct only |
| Debounce / redundant-update suppression | ✅ |
| Publish-safe config defaults | ✅ |

## Backend Support Matrix

| Surface | Hue direct | Hubitat Maker API | Govee via Hubitat |
|---|---:|---:|---:|
| Hermes plugin hooks | ✅ recommended | ⚠️ supported as legacy fallback | ⚠️ best-effort; device-driver dependent |
| Desktop plugin companion | ✅ | ❌ not currently implemented | ❌ not currently implemented |

**Recommendation:** use **Philips Hue direct bridge control** if available. It is lower-latency, avoids Hubitat/Govee RGB↔CT mode quirks, and is the best-tested path.

The Hubitat backend is retained for users who already expose a light through Hubitat Maker API. It may also work with Hubitat-connected Govee devices, but Govee behavior depends heavily on the Hubitat driver and device mode. Some Govee/Hubitat combinations can silently accept commands without visibly changing the light.

## State Model

| Agent state | Meaning | Default color |
|---|---|---|
| `THINKING` | Agent is actively processing | Red for local models, purple for cloud models, amber for cron |
| `WAITING` | Agent is waiting for approval | Blue |
| `IDLE` | Agent finished and is ready | Green |

## Repository Layout

```text
.
├── __init__.py                     # Hermes plugin hooks (gateway/TUI/WebUI/cron)
├── plugin.yaml                     # Hermes plugin manifest
├── dashboard/
│   ├── manifest.json              # API manifest for the Hermes plugin package
│   └── plugin_api.py              # Hue-only REST endpoint used by bundled API surface
├── desktop-plugin/
│   ├── manifest.json              # Hermes Desktop plugin manifest
│   ├── plugin.js                  # Desktop frontend polling/status widget
│   └── dashboard/
│       └── plugin_api.py          # Hue-only Desktop REST endpoint for light updates
├── tests/                         # Unit tests for backend/state behavior
└── README.md
```

## How It Works

### Hermes plugin surface

Uses Hermes lifecycle hooks:

- `pre_llm_call` → `THINKING`
- `post_llm_call` → `IDLE`
- `pre_approval_request` → `WAITING`
- `post_approval_response` → `THINKING`
- `on_session_start` → logging/visibility only

### Model-aware colors

- **Local GGUF models** → red thinking state
- **Cloud/provider-hosted models** → purple thinking state
- **Cron platform** → amber thinking state

### Desktop surface

The desktop plugin polls for active/running sessions and updates the same light via a small REST bridge. The Desktop companion currently supports **Hue direct only**.

## Configuration

All runtime configuration is env-var driven.

### Common

```bash
LIGHT_BACKEND="hue"   # Hermes plugin only: hue or hubitat. Defaults to hue.
LIGHT_ON_LLM_LOG_FILE="/tmp/light_on_llm.log"
LIGHT_ON_LLM_DESKTOP_LOG_FILE="/tmp/light_on_llm_desktop.log"
```

### Philips Hue direct bridge control — recommended

```bash
HUE_BRIDGE_URL="http://YOUR-HUE-BRIDGE-IP"
HUE_API_KEY="your-hue-api-key"
HUE_LIGHT_ID="your-light-id"
```

Create a Hue API key by pressing the physical link button on the bridge, then within 30 seconds:

```bash
curl -X POST "http://YOUR-HUE-BRIDGE-IP/api" \
  -d '{"devicetype":"hermes-agent:light-on-llm"}'
```

Use the returned `username` as `HUE_API_KEY`.

### Hubitat Maker API fallback — legacy / best-effort

```bash
LIGHT_BACKEND="hubitat"
HUBITAT_BASE_URL="http://YOUR-HUBITAT-IP/apps/api/YOUR_APP_ID/devices/YOUR_DEVICE_ID"
HUBITAT_ACCESS_TOKEN="your-hubitat-maker-api-token"
```

Hubitat colors use Hubitat's `0-100` hue scale, not Hue Bridge's `0-65535` scale.

### Notes on Govee via Hubitat

Govee lights connected through Hubitat may work, but this path is explicitly **best-effort**. Known issues include:

- some drivers ignore `level` inside `setColor`
- some devices hang on `setLevel`
- RGB/CT mode changes may cause silent command drops
- Hubitat may return HTTP 200 even when the light did not actually change

If you are posting results publicly or want the most reliable indicator, use Hue direct.

## Installation

### 1) Hermes plugin: gateway / TUI / WebUI / cron

Clone the repo into the standard Hermes plugin location:

```bash
git clone https://github.com/Cali-ghub/hermes-light-on-llm.git ~/.hermes/plugins/light-on-llm
```

Enable it in `~/.hermes/config.yaml`:

```yaml
plugins:
  enabled:
    - light-on-llm
```

Restart Hermes gateway after configuration changes.

### 2) Hermes Desktop plugin companion

Copy the desktop package into the Hermes Desktop plugins directory:

```bash
mkdir -p ~/.hermes/desktop-plugins/light-on-llm
cp -R ~/.hermes/plugins/light-on-llm/desktop-plugin/* ~/.hermes/desktop-plugins/light-on-llm/
```

This package contains its own `manifest.json`, `plugin.js`, and REST backend.

## Testing

Run the local sanity suite:

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q .
python3 -m json.tool dashboard/manifest.json >/dev/null
python3 -m json.tool desktop-plugin/manifest.json >/dev/null
```

## Publish / privacy notes

This repository intentionally avoids bundling:

- personal names in plugin metadata
- live bridge IPs
- live access tokens or API keys
- environment-specific scene IDs
- household- or device-specific labels

If you fork or redistribute it, keep secrets in `.env` or your platform-specific secret manager.

## Verification checklist

Before release:

- [ ] Python sources compile cleanly
- [ ] JSON manifests parse cleanly
- [ ] Unit tests pass
- [ ] No hardcoded bridge IPs or API keys remain
- [ ] Desktop plugin files are present
- [ ] README matches actual capabilities

## Versioning

This repo should be treated as **v2.x** and later if the combined Hermes + Desktop support remains part of the public contract. Patch releases may adjust backend compatibility or documentation without changing the public plugin shape.
