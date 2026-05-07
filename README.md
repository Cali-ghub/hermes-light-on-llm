# light-on-llm — Hermes Agent Plugin

Controls a Hubitat-connected smart light based on LLM agent state. Provides at-a-glance visual feedback for long-running AI tasks.

## States

| State | Color | When |
|-------|-------|------|
| **THINKING** | 🔴 Red (dim) | Agent is processing — LLM calls, tool execution, multi-step workflows |
| **WAITING** | 🔵 Blue | Agent needs user approval for a dangerous command |
| **IDLE** | 🟡 Warm White (very dim) | Agent finished, ready for next prompt |

## How It Works

Uses Hermes Agent plugin hooks — no core modifications:

- `pre_llm_call` → Red (fires once per complete agent run)
- `post_llm_call` → Warm White (fires after ALL turns finish)
- `pre_approval_request` → Blue (approval prompt shown)
- `post_approval_response` → Red (agent resumes after approval)

Works across **TUI, WebUI, Signal, Telegram** — any platform that loads Hermes plugins.

## Requirements

- [Hermes Agent](https://github.com/nousresearch/hermes-agent) installed
- Hubitat hub with a color-capable light (tested with Philips Hue)
- Python `requests` library (usually already present in Hermes venv)

## Installation

### 1. Install the Plugin

```bash
# Clone into your Hermes plugins directory
git clone https://github.com/Cali-ghub/hermes-light-on-llm.git ~/.hermes/plugins/light-on-llm
```

### 2. Configure Hubitat Credentials

Add to `~/.hermes/.env`:

```bash
HUBITAT_BASE_URL="http://YOUR-HUBITAT-IP/apps/api/YOUR_APP_ID/devices/YOUR_DEVICE_ID"
HUBITAT_ACCESS_TOKEN="your-hubitat-maker-api-token"
```

**Finding your values:**

| Variable | Where to Find It |
|----------|------------------|
| `YOUR-HUBITAT-IP` | Your Hubitat hub's LAN IP (e.g., `192.168.1.100`) |
| `YOUR_APP_ID` | Maker API app ID — check the URL when viewing your Maker API config in Hubitat (`/apps/api/APP_ID/...`) |
| `YOUR_DEVICE_ID` | Device number from Hubitat's Devices page (e.g., `613` for a Hue bulb) |
| `ACCESS_TOKEN` | "Access Token" field on the Maker API configuration page |

### 3. Enable the Plugin

Add to `~/.hermes/config.yaml`:

```yaml
plugins:
  enabled:
    - light-on-llm
```

### 4. Restart Hermes Gateway

```bash
sudo systemctl restart hermes-gateway
# Or if running manually:
hermes gateway run --replace
```

## Adapting for Other Smart Home Platforms

The plugin uses Hubitat's Maker API endpoints (`/setColor`, `/setColorTemperature`, `/setLevel`). To adapt for other platforms, modify `_set_color()` and `_set_color_temperature()` in `__init__.py`:

| Platform | Approach |
|----------|----------|
| **Home Assistant** | Replace with REST API calls: `POST /api/services/light/turn_on` with `color_hs`, `brightness`, `color_temp` |
| **Philips Hue Bridge** | Direct bridge API: `PUT /api/user/lights/{id}/state` |
| **SmartThings** | SmartThings API v2: `PATCH /v1/devices/{id}` |

The hook registration and state machine logic stays the same — only the two `_set_*` functions need changing.

## Log File

Runtime logs written to `/tmp/light_on_llm.log`. Useful for debugging state transitions or API errors.

## Architecture

- **Zero core modifications** — pure plugin, survives Hermes updates
- **In-memory state tracking** — no shared files, no race conditions
- **Deduplication** — skips redundant API calls when state hasn't changed
- **Env var config** — credentials never in code, safe for version control

## Author

Jason Callahan — [Cali-ghub](https://github.com/Cali-ghub)
