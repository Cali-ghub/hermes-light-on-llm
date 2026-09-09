# light-on-llm Plugin for Hermes Agent
# Controls a smart light based on LLM agent state.
# pre_llm_call → THINKING (local=red, cloud=purple, cron=amber), post_llm_call → IDLE (green)
# pre_approval_request → WAITING (blue), post_approval_response → THINKING
import datetime
import json
import os
import time
from typing import Optional
from urllib.parse import quote, urlencode

# --- Logging (direct file I/O — Hermes suppresses stdlib logging in plugins) ---
LOG_FILE = os.environ.get("LIGHT_ON_LLM_LOG_FILE", "/tmp/light_on_llm.log")


def _log(msg: str) -> None:
    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(LOG_FILE, 'a') as f:
        f.write(f"{ts} - [plugin] {msg}\n")


_log("Plugin module loaded (light-on-llm).")

# --- Configuration ---
BACKEND = os.environ.get("LIGHT_BACKEND", "hue").lower()

HUE_BRIDGE_URL = os.environ.get(
    "HUE_BRIDGE_URL",
    "http://YOUR-HUE-BRIDGE-IP"
).rstrip("/")
HUE_API_KEY = os.environ.get("HUE_API_KEY", "")
HUE_LIGHT_ID = os.environ.get("HUE_LIGHT_ID", "")

# Direct xy color coordinates and Hue values.
# These are generic defaults for the state palette, not user-specific secrets.
THINKING_LOCAL_XY = [0.6915, 0.3083]
THINKING_CLOUD_HUE = 50000
THINKING_CRON_HUE = 10000
WAITING_HUE = 46920
IDLE_XY = [0.2098, 0.5407]
THINKING_BRI = 25
WAITING_BRI = 50
IDLE_BRI = 5

_log(f"Backend: {BACKEND}")

# --- State tracking (single global state — one light, no session juggling) ---
_current_state = "IDLE"
_last_light_color = None
_last_scene_time = 0.0
_DEBOUNCE_SECS = 1.5


def _should_send() -> bool:
    global _last_scene_time
    now = time.monotonic()
    if (now - _last_scene_time) < _DEBOUNCE_SECS:
        return False
    _last_scene_time = now
    return True


# ====================================================================
# Hue Bridge backend (direct light state writes — no scenes)
# ====================================================================
def _hue_set_state(payload: dict) -> bool:
    """Set light state via direct PUT to /lights/{id}/state."""
    if not HUE_API_KEY or not HUE_LIGHT_ID:
        _log("Hue config incomplete: HUE_API_KEY and HUE_LIGHT_ID are required")
        return False

    url = f"{HUE_BRIDGE_URL}/api/{HUE_API_KEY}/lights/{HUE_LIGHT_ID}/state"
    for attempt in range(3):
        try:
            import urllib.request
            data = json.dumps(payload).encode()
            resp = urllib.request.urlopen(
                urllib.request.Request(url, data=data, method="PUT"), timeout=5
            )
            result = json.loads(resp.read())
            ok = sum(1 for item in result if isinstance(item, dict) and "success" in item)
            errs = [item for item in result if isinstance(item, dict) and "error" in item]
            if errs:
                _log(f"Hue partial: {ok} ok, errors: {[e.get('error',{}).get('description','?') for e in errs]}")
            elif ok > 0:
                _log(f"Hue OK: {payload}")
                return True
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))
        except Exception as e:
            if attempt < 2:
                _log(f"Hue retry {attempt+1}: {e}")
                time.sleep(0.5 * (attempt + 1))
    _log(f"Hue FAILED after retries: {payload}")
    return False


def _hue_set_color(hue_16bit: int, sat_byte: int, bri_byte: int) -> bool:
    return _hue_set_state({"hue": hue_16bit, "sat": sat_byte, "bri": bri_byte, "on": True})


def _hue_set_xy(xy: list, bri_byte: int) -> bool:
    return _hue_set_state({"xy": xy, "bri": bri_byte, "on": True})


# ====================================================================
# Hubitat Maker API backend (legacy fallback)
# ====================================================================
HUBITAT_BASE = os.environ.get(
    "HUBITAT_BASE_URL",
    "http://YOUR-HUBITAT-IP/apps/api/YOUR_APP_ID/devices/YOUR_DEVICE_ID"
)
ACCESS_TOKEN = os.environ.get("HUBITAT_ACCESS_TOKEN", "")


def _hubitat_url(command_path: str) -> str:
    """Build a Hubitat Maker API command URL with a correctly separated token query."""
    return f"{HUBITAT_BASE.rstrip('/')}/{command_path.lstrip('/')}?{urlencode({'access_token': ACCESS_TOKEN})}"


def _require_hubitat_config() -> bool:
    if not ACCESS_TOKEN:
        _log("Hubitat config incomplete: HUBITAT_ACCESS_TOKEN is required")
        return False
    if "YOUR-HUBITAT-IP" in HUBITAT_BASE or "YOUR_APP_ID" in HUBITAT_BASE or "YOUR_DEVICE_ID" in HUBITAT_BASE:
        _log("Hubitat config incomplete: HUBITAT_BASE_URL still contains placeholder values")
        return False
    return True


def _hubitat_set_color(hue: int, saturation: int, level: int) -> bool:
    if not _require_hubitat_config():
        return False

    payload = quote(json.dumps({"hue": hue, "saturation": saturation, "level": level}, separators=(",", ":")), safe="")
    command_path = f"setColor/{payload}"
    try:
        import urllib.request
        resp = urllib.request.urlopen(_hubitat_url(command_path), timeout=5)
        if resp.status == 200:
            _log(f"Hubitat setColor OK (hue={hue}, sat={saturation}, level={level})")
            return True
    except Exception as e:
        _log(f"Hubitat setColor error: {e}")
    return False


def _hubitat_set_color_temperature(temp: int, level: int) -> bool:
    if not _require_hubitat_config():
        return False

    try:
        import urllib.request
        r1 = urllib.request.urlopen(_hubitat_url(f"setColorTemperature/{temp}"), timeout=5)
        r2 = urllib.request.urlopen(_hubitat_url(f"setLevel/{level}"), timeout=5)
        ok = (r1.status == 200 and r2.status == 200)
        if ok:
            _log(f"Hubitat setCT OK (temp={temp}K, level={level})")
        return ok
    except Exception as e:
        _log(f"Hubitat setCT error: {e}")
        return False


# ====================================================================
# Unified transition function
# ====================================================================
def _is_cloud_model(model: str) -> bool:
    if not model:
        return False
    return not model.endswith('.gguf')


def _is_cron_platform(platform: Optional[str]) -> bool:
    return str(platform or "").strip().lower() == "cron"


def _light_spec(state: str, *, model: Optional[str] = None, platform: Optional[str] = None) -> tuple[str, tuple]:
    """Return a symbolic color key plus backend payload spec."""
    if state == "THINKING":
        if _is_cron_platform(platform):
            return "cron", ("hue", THINKING_CRON_HUE, 255, THINKING_BRI)
        if model and _is_cloud_model(model):
            return "purple", ("hue", THINKING_CLOUD_HUE, 255, THINKING_BRI)
        return "red", ("xy", THINKING_LOCAL_XY, THINKING_BRI)
    if state == "WAITING":
        return "blue", ("hue", WAITING_HUE, 255, WAITING_BRI)
    if state == "IDLE":
        return "green", ("xy", IDLE_XY, IDLE_BRI)
    return "unknown", tuple()


def _set_light(state: str, *, model: Optional[str] = None, platform: Optional[str] = None) -> bool:
    """Actually set the light to a given state. Returns True only when the backend accepts it."""
    global _last_light_color

    color_key, _spec = _light_spec(state, model=model, platform=platform)
    if color_key == "unknown":
        return False

    if _last_light_color == color_key:
        return True

    if not _should_send():
        _log(f"SKIP (debounce): {state} too soon")
        return False

    _log(f"LIGHT SET: {state} ({color_key})")
    ok = False

    if BACKEND == "hue":
        if state == "THINKING":
            if color_key == "cron":
                _log(f"THINKING (cron: {model})")
                ok = _hue_set_color(hue_16bit=THINKING_CRON_HUE, sat_byte=255, bri_byte=THINKING_BRI)
            elif model and _is_cloud_model(model):
                _log(f"THINKING (cloud: {model})")
                ok = _hue_set_color(hue_16bit=THINKING_CLOUD_HUE, sat_byte=255, bri_byte=THINKING_BRI)
            else:
                _log(f"THINKING (local: {model})")
                ok = _hue_set_xy(xy=THINKING_LOCAL_XY, bri_byte=THINKING_BRI)
        elif state == "WAITING":
            ok = _hue_set_color(hue_16bit=WAITING_HUE, sat_byte=255, bri_byte=WAITING_BRI)
        elif state == "IDLE":
            ok = _hue_set_xy(xy=IDLE_XY, bri_byte=IDLE_BRI)
    elif BACKEND == "hubitat":
        if state == "THINKING":
            if color_key == "cron":
                ok = _hubitat_set_color(hue=30, saturation=100, level=10)
            elif model and _is_cloud_model(model):
                ok = _hubitat_set_color(hue=80, saturation=100, level=10)
            else:
                ok = _hubitat_set_color(hue=0, saturation=100, level=10)
        elif state == "WAITING":
            ok = _hubitat_set_color(hue=70, saturation=100, level=20)
        elif state == "IDLE":
            ok = _hubitat_set_color_temperature(temp=2700, level=5)
    else:
        _log(f"Unknown LIGHT_BACKEND={BACKEND!r}; expected 'hue' or 'hubitat'")

    if ok:
        _last_light_color = color_key
    else:
        _log(f"LIGHT SET FAILED: {state} ({color_key})")
    return ok


def _transition_to(new_state: str, *, model: Optional[str] = None, platform: Optional[str] = None) -> None:
    """Transition to a new global state."""
    global _current_state

    if _current_state == new_state and not model and not platform:
        return

    _log(f"TRANSITION: {new_state} (was: {_current_state})")
    _current_state = new_state
    _set_light(new_state, model=model, platform=platform)


# ====================================================================
# Hook handlers — using standard Hermes plugin hooks
# ====================================================================
def on_pre_llm_call(**kwargs):
    model = kwargs.get('model', '')
    platform = kwargs.get('platform', '')
    _log(f"pre_llm_call [model={model} platform={platform}]")
    _transition_to("THINKING", model=model, platform=platform)


def on_post_llm_call(**kwargs):
    platform = kwargs.get('platform', '')
    _log("post_llm_call: agent finished this turn")
    _transition_to("IDLE", platform=platform)


def on_pre_approval_request(**kwargs):
    cmd = kwargs.get('command', 'unknown')
    _log(f"pre_approval_request: {cmd}")
    _transition_to("WAITING")


def on_post_approval_response(**kwargs):
    response = kwargs.get('choice', kwargs.get('response', '?'))
    model = kwargs.get('model', '')
    _log(f"post_approval_response: {response}")
    _transition_to("THINKING", model=model)


def on_session_start(**kwargs):
    _log(
        f"SESSION START [session_id={kwargs.get('session_id','?')} model={kwargs.get('model','?')} platform={kwargs.get('platform','?')}]"
    )


def register(ctx):
    _log("Registering Light-on-LLM plugin hooks...")

    ctx.register_hook("pre_llm_call", on_pre_llm_call)
    ctx.register_hook("post_llm_call", on_post_llm_call)
    ctx.register_hook("on_session_start", on_session_start)
    ctx.register_hook("pre_approval_request", on_pre_approval_request)
    ctx.register_hook("post_approval_response", on_post_approval_response)

    _log("All hooks registered successfully.")
