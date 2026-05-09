# light-on-llm Plugin for Hermes Agent
# Controls a smart light based on LLM agent state.
# pre_llm_call → THINKING (LLMRed scene), post_llm_call → IDLE (idle green scene)
# pre_approval_request → WAITING (Blue)
# Supports: Philips Hue Bridge (direct, with scenes) or Hubitat Maker API
import datetime
import json
import logging
import os
import requests

# --- Logging ---
LOG_FILE = "/tmp/light_on_llm.log"


def _log(msg: str) -> None:
    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(LOG_FILE, 'a') as f:
        f.write(f"{ts} - [plugin] {msg}\n")


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.FileHandler(LOG_FILE)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

_log("Plugin module loaded by Hermes (light-on-llm).")

# --- Configuration ---
# Backend selection: "hue" (default, direct bridge API) or "hubitat" (Maker API)
BACKEND = os.environ.get("LIGHT_BACKEND", "hue").lower()

# Hue Bridge config
HUE_BRIDGE_URL = os.environ.get(
    "HUE_BRIDGE_URL",
    "http://YOUR-HUE-BRIDGE-IP"
).rstrip("/")
HUE_API_KEY = os.environ.get("HUE_API_KEY", "")
HUE_LIGHT_ID = os.environ.get("HUE_LIGHT_ID", "")

# Hue scenes (set via env or use defaults)
HUE_SCENE_THINKING = os.environ.get("HUE_SCENE_THINKING", "bbaDpbTROOPyFlAX")   # LLMRed
HUE_SCENE_IDLE = os.environ.get("HUE_SCENE_IDLE", "LNj1u7P3zMF2I5RN")           # idle green

# Hubitat config (fallback)
HUBITAT_BASE = os.environ.get(
    "HUBITAT_BASE_URL",
    "http://YOUR-HUBITAT-IP/apps/api/YOUR_APP_ID/devices/YOUR_DEVICE_ID"
)
ACCESS_TOKEN = os.environ.get("HUBITAT_ACCESS_TOKEN", "")

_log(f"Backend: {BACKEND}")


# --- State tracking (in-memory per process) ---
_current_state = None  # Track state within this plugin instance


# ====================================================================
# Hue Bridge backend (direct API)
# ====================================================================
def _hue_set_color(hue_16bit: int, sat_byte: int, bri_byte: int) -> bool:
    """Set RGB color via Hue bridge.
    
    Hue uses 16-bit hue (0-65535), 8-bit saturation (0-255), 8-bit brightness (0-255).
    """
    url = f"{HUE_BRIDGE_URL}/api/{HUE_API_KEY}/lights/{HUE_LIGHT_ID}/state"
    payload = {
        "hue": hue_16bit,
        "sat": sat_byte,
        "bri": bri_byte,
        "on": True
    }
    try:
        resp = requests.put(url, json=payload, timeout=5)
        data = resp.json()
        # Hue returns array of per-parameter results
        successes = sum(1 for item in data if isinstance(item, dict) and "success" in item)
        errors = [item for item in data if isinstance(item, dict) and "error" in item]
        if errors:
            _log(f"Hue setColor partial: {successes} ok, errors: {[e.get('error',{}).get('description','?') for e in errors]}")
        elif successes > 0:
            _log(f"Hue setColor OK (hue={hue_16bit}, sat={sat_byte}, bri={bri_byte})")
        return successes > 0
    except Exception as e:
        _log(f"Hue setColor error: {e}")
        return False


def _hue_set_ct(ct: int, bri_byte: int) -> bool:
    """Set color temperature via Hue bridge.

    ct is in mireds (153-500). Lower = warmer, higher = cooler.
    454 ≈ 2700K warm white.
    """
    url = f"{HUE_BRIDGE_URL}/api/{HUE_API_KEY}/lights/{HUE_LIGHT_ID}/state"
    payload = {
        "ct": ct,
        "bri": bri_byte,
        "on": True
    }
    try:
        resp = requests.put(url, json=payload, timeout=5)
        data = resp.json()
        successes = sum(1 for item in data if isinstance(item, dict) and "success" in item)
        if successes > 0:
            _log(f"Hue setCT OK (ct={ct}, bri={bri_byte})")
        return successes > 0
    except Exception as e:
        _log(f"Hue setCT error: {e}")
        return False


def _hue_recall_scene(scene_id: str) -> bool:
    """Recall a Hue scene by ID.

    GroupScenes require recalling via /groups/{group}/action with {"scene": id}.
    LightScenes can use /scenes/{id}/action directly.
    We try group recall first (works for both), then fall back to direct.
    """
    # Try group-based recall (works for GroupScene and all-lights)
    url = f"{HUE_BRIDGE_URL}/api/{HUE_API_KEY}/groups/0/action"
    payload = {"scene": scene_id}
    try:
        resp = requests.put(url, json=payload, timeout=5)
        data = resp.json()
        successes = sum(1 for item in data if isinstance(item, dict) and "success" in item)
        errors = [item for item in data if isinstance(item, dict) and "error" in item]
        if errors:
            _log(f"Hue scene recall partial ({scene_id}): {successes} ok, errors: {[e.get('error',{}).get('description','?') for e in errors]}")
        elif successes > 0:
            _log(f"Hue scene OK ({scene_id})")
        return successes > 0
    except Exception as e:
        _log(f"Hue scene recall error ({scene_id}): {e}")
        return False


# ====================================================================
# Hubitat Maker API backend (legacy)
# ====================================================================
def _hubitat_set_color(hue: int, saturation: int, level: int) -> bool:
    url = f"{HUBITAT_BASE}/setColor/%7B%22hue%22:{hue}%2C%22saturation%22:{saturation}%2C%22level%22:{level}%7D"
    try:
        resp = requests.get(url, params={"access_token": ACCESS_TOKEN}, timeout=5)
        if resp.status_code == 200:
            _log(f"Hubitat setColor OK (hue={hue}, sat={saturation}, level={level})")
            return True
        else:
            _log(f"Hubitat setColor failed: HTTP {resp.status_code}")
            return False
    except Exception as e:
        _log(f"Hubitat setColor error: {e}")
        return False


def _hubitat_set_color_temperature(temp: int, level: int) -> bool:
    try:
        resp1 = requests.get(
            f"{HUBITAT_BASE}/setColorTemperature/{temp}",
            params={"access_token": ACCESS_TOKEN}, timeout=5
        )
        resp2 = requests.get(
            f"{HUBITAT_BASE}/setLevel/{level}",
            params={"access_token": ACCESS_TOKEN}, timeout=5
        )
        ok1 = resp1.status_code == 200
        ok2 = resp2.status_code == 200
        if ok1 and ok2:
            _log(f"Hubitat setColorTemperature OK (temp={temp}K, level={level})")
            return True
        else:
            _log(
                f"Hubitat setCT failed: setColorTemp HTTP {resp1.status_code}, setLevel HTTP {resp2.status_code}"
            )
            return False
    except Exception as e:
        _log(f"Hubitat setColorTemperature error: {e}")
        return False


# ====================================================================
# Unified transition function
# ====================================================================
def _transition_to(new_state: str) -> None:
    """Transition to a new state, skipping if already in that state."""
    global _current_state

    if _current_state == new_state:
        _log(f"SKIP: already in state {new_state}")
        return

    old = _current_state
    _current_state = new_state
    _log(f"STATE CHANGE: {new_state} (was: {old})")

    if BACKEND == "hue":
        # Use Hue scenes for THINKING and IDLE, direct color for WAITING
        if new_state == "THINKING":
            _hue_recall_scene(HUE_SCENE_THINKING)       # LLMRed scene
        elif new_state == "WAITING":
            _hue_set_color(hue_16bit=46920, sat_byte=255, bri_byte=25)   # Blue (~280° in 16-bit)
        elif new_state == "IDLE":
            _hue_recall_scene(HUE_SCENE_IDLE)           # idle green scene

    else:
        # Hubitat uses 0-100 hue, 0-100 saturation, 0-100 level
        if new_state == "THINKING":
            _hubitat_set_color(hue=0, saturation=100, level=10)           # Red
        elif new_state == "WAITING":
            _hubitat_set_color(hue=70, saturation=100, level=10)          # Blue
        elif new_state == "IDLE":
            _hubitat_set_color_temperature(temp=2700, level=10)           # Warm white


def on_llm_call_start(**kwargs):
    """Fired once per turn, before the tool-calling loop begins."""
    _log("pre_llm_call: agent started thinking")
    _transition_to("THINKING")


def on_llm_call_end(**kwargs):
    """Fired once per turn, after the tool-calling loop completes."""
    _log("post_llm_call: agent finished this turn")
    _transition_to("IDLE")


def on_approval_request(**kwargs):
    """Fired when the agent needs user approval for a dangerous command."""
    cmd = kwargs.get('command', 'unknown')
    _log(f"pre_approval_request: {cmd}")
    _transition_to("WAITING")


def on_approval_response(**kwargs):
    """Fired after user approves/denies — agent resumes processing."""
    response = kwargs.get('response', 'unknown')
    cmd = kwargs.get('command', 'unknown')
    _log(f"post_approval_response: {response} for {cmd}")
    # Agent is back to thinking after approval
    _transition_to("THINKING")


def register(ctx):
    """Register all plugin hooks for full state control."""
    _log("Registering Light-on-LLM plugin hooks (full state)...")

    ctx.register_hook("pre_llm_call", on_llm_call_start)
    ctx.register_hook("post_llm_call", on_llm_call_end)
    ctx.register_hook("pre_approval_request", on_approval_request)
    ctx.register_hook("post_approval_response", on_approval_response)

    _log("All plugin hooks registered successfully.")
