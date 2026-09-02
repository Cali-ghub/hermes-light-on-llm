# light-on-llm

A visual status indicator for Hermes Agent that drives a smart light based on agent state.

This repo now covers **both plugin surfaces**:

1. **Hermes plugin** for gateway / TUI / WebUI / cron runs
2. **Hermes Desktop plugin** for the desktop app surface

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
| Philips Hue direct light writes | ✅ |
| Hubitat Maker API fallback | ✅ |
| Desktop plugin support | ✅ |
| Debounce / redundant-update suppression | ✅ |
| Publish-safe config defaults | ✅ |

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
│   └── plugin_api.py              # Shared REST endpoint for local light updates
├── desktop-plugin/
│   ├── manifest.json              # Hermes Desktop plugin manifest
│   ├── plugin.js                  # Desktop frontend polling/status widget
│   └── dashboard/
│       └── plugin_api.py          # Desktop REST endpoint for light updates
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
The desktop plugin polls for active/running sessions and updates the same light via a small REST bridge.

## Configuration

All runtime configuration is env-var driven.

### Common
```bash
LIGHT_BACKEND="hue"   # or: hubitat
LIGHT_ON_LLM_LOG_FILE="/tmp/light_on_llm.log"
```

### Philips Hue
```bash
HUE_BRIDGE_URL="http://YOUR-HUE-BRIDGE-IP"
HUE_API_KEY="your-hue-api-key"
HUE_LIGHT_ID="your-light-id"
```

### Hubitat Maker API
```bash
HUBITAT_BASE_URL="http://YOUR-HUBITAT-IP/apps/api/YOUR_APP_ID/devices/YOUR_DEVICE_ID"
HUBITAT_ACCESS_TOKEN="your-hubitat-maker-api-token"
```

## Installation

## 1) Hermes plugin (gateway / TUI / WebUI / cron)
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

## 2) Hermes Desktop plugin
Copy the desktop package into the Hermes Desktop plugins directory:

```bash
mkdir -p ~/.hermes/desktop-plugins/light-on-llm
cp -R ~/.hermes/plugins/light-on-llm/desktop-plugin/* ~/.hermes/desktop-plugins/light-on-llm/
```

This package contains its own `manifest.json`, `plugin.js`, and REST backend.

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
- [ ] No hardcoded bridge IPs or API keys remain
- [ ] Desktop plugin files are present
- [ ] README matches actual capabilities

## Versioning

This repo should be treated as **v2.x** and later if the combined Hermes + Desktop support remains part of the public contract.
