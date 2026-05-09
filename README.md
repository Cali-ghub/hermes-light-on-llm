# light-on-llm — Hermes Agent Plugin

Controls a smart light based on LLM agent state. Provides at-a-glance visual feedback for long-running AI tasks. Supports **Philips Hue Bridge** (direct API) and **Hubitat Maker API** backends.

## States

| State | Color | When |
|-------|-------|------|
| **THINKING** | 🔴 Red (dim) | Agent is processing — LLM calls, tool execution, multi-step workflows |
| **WAITING** | 🔵 Blue | Agent needs user approval for a dangerous command |
| **IDLE** | 🟢 Green (very dim) | Agent finished, ready for next prompt |

## How It Works

Uses Hermes Agent plugin hooks — no core modifications:

- `pre_llm_call` → Red (fires once per complete agent run)
- `post_llm_call` → Green (fires after ALL turns finish)
- `pre_approval_request` → Blue (approval prompt shown)
- `post_approval_response` → Red (agent resumes after approval)

Works across **TUI, WebUI, Signal, Telegram** — any platform that loads Hermes plugins.

## Backends

| Backend | Pros | Cons |
|---------|------|------|
| **Hue Bridge** (default) | Lower latency (~50ms), precise color, scene support | Requires Hue bridge + API key |
| **Hubitat** | Single intermediary for mixed ecosystems, no extra auth | Extra hop (~200-400ms), less granular color control |

Set via `LIGHT_BACKEND` env var (`hue` or `hubitat`). Defaults to `hue`.

## Installation

### 1. Clone the Plugin

```bash
git clone https://github.com/Cali-ghub/hermes-light-on-llm.git ~/.hermes/plugins/light-on-llm
```

### 2. Configure Your Backend

#### Option A: Philips Hue Bridge (recommended)

Add to `~/.hermes/.env`:

```bash
LIGHT_BACKEND="hue"
HUE_BRIDGE_URL="http://YOUR-HUE-BRIDGE-IP"
HUE_API_KEY="your-hue-api-key"
HUE_LIGHT_ID="31"
# Optional: override scene IDs (defaults work if you use the same scenes)
# HUE_SCENE_THINKING="..."   # e.g. a red scene named "LLMRed"
# HUE_SCENE_IDLE="..."       # e.g. a green scene named "idle green"
```

**Finding your values:**

| Variable | Where to Find It |
|----------|------------------|
| `HUE_BRIDGE_URL` | Your Hue bridge LAN IP (e.g., `http://192.168.1.x`) |
| `HUE_API_KEY` | Generate by pressing the link button on your bridge and sending `POST /api/devicetype` — see [Philips Hue API docs](https://developers.meethue.com/) |
| `HUE_LIGHT_ID` | Light number from `GET /api/key/lights` (e.g., `31`) |
| `HUE_SCENE_THINKING` | Scene ID from `GET /api/key/scenes` — create scenes in the Hue app for THINKING and IDLE states |

**Scene setup:** Create two scenes in the Hue app:
- **THINKING**: Red, dim (~30% brightness) — name it "LLMRed" or similar
- **IDLE**: Green, very dim (~10% brightness) — name it "idle green" or similar

Scenes are recalled for THINKING and IDLE states. WAITING uses direct blue color.

#### Option B: Hubitat Maker API (legacy)

Add to `~/.hermes/.env`:

```bash
LIGHT_BACKEND="hubitat"
HUBITAT_BASE_URL="http://YOUR-HUBITAT-IP/apps/api/YOUR_APP_ID/devices/YOUR_DEVICE_ID"
HUBITAT_ACCESS_TOKEN="your-hubitat-maker-api-token"
```

| Variable | Where to Find It |
|----------|------------------|
| `YOUR-HUBITAT-IP` | Your Hubitat hub's LAN IP (e.g., `192.168.1.100`) |
| `YOUR_APP_ID` | Maker API app ID from the URL (`/apps/api/APP_ID/...`) |
| `YOUR_DEVICE_ID` | Device number from Hubitat's Devices page (e.g., `613`) |
| `ACCESS_TOKEN` | "Access Token" field on the Maker API config page |

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

The plugin architecture supports any HTTP-based smart home API. Add a new backend by:

1. Creating `_yourplatform_*()` functions in `__init__.py`
2. Adding your platform name to the `BACKEND` env var check
3. Wiring state transitions in `_transition_to()`

| Platform | Approach |
|----------|----------|
| **Home Assistant** | `POST /api/services/light/turn_on` with `color_hs`, `brightness`, `color_temp` |
| **SmartThings** | SmartThings API v2: `PATCH /v1/devices/{id}` |

The hook registration and state machine logic stays the same — only the `_set_*` functions need changing.

## Log File

Runtime logs written to `/tmp/light_on_llm.log`. Useful for debugging state transitions or API errors.

## Architecture

- **Zero core modifications** — pure plugin, survives Hermes updates
- **In-memory state tracking** — no shared files, no race conditions
- **Deduplication** — skips redundant API calls when state hasn't changed
- **Env var config** — credentials never in code, safe for version control

## Author

[Cali-ghub](https://github.com/Cali-ghub)
