# light-on-llm Plugin for Hermes Agent
# Controls a Hubitat-connected smart light based on LLM agent state.
# pre_llm_call → THINKING (Red), post_llm_call → IDLE (Warm White)
# pre_approval_request → WAITING (Blue)
import datetime
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

# --- Hubitat Configuration ---
# Set these via environment variables or ~/.hermes/.env:
#   HUBITAT_BASE_URL  = e.g. http://192.168.1.100/apps/api/277/devices/613
#   HUBITAT_ACCESS_TOKEN = your Hubitat Maker API access token
HUBITAT_BASE = os.environ.get(
    "HUBITAT_BASE_URL",
    "http://YOUR-HUBITAT-IP/apps/api/YOUR_APP_ID/devices/YOUR_DEVICE_ID"
)
ACCESS_TOKEN = os.environ.get("HUBITAT_ACCESS_TOKEN", "")

# --- State tracking (in-memory per process) ---
_current_state = None  # Track state within this plugin instance


def _set_color(hue: int, saturation: int, level: int) -> bool:
    url = f"{HUBITAT_BASE}/setColor/%7B%22hue%22:{hue}%2C%22saturation%22:{saturation}%2C%22level%22:{level}%7D"
    try:
        resp = requests.get(url, params={"access_token": ACCESS_TOKEN}, timeout=5)
        if resp.status_code == 200:
            _log(f"setColor OK (hue={hue}, sat={saturation}, level={level})")
            return True
        else:
            _log(f"setColor failed: HTTP {resp.status_code}")
            return False
    except Exception as e:
        _log(f"setColor error: {e}")
        return False


def _set_color_temperature(temp: int, level: int) -> bool:
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
            _log(f"setColorTemperature OK (temp={temp}K, level={level})")
            return True
        else:
            _log(
                f"setCT failed: setColorTemp HTTP {resp1.status_code}, setLevel HTTP {resp2.status_code}"
            )
            return False
    except Exception as e:
        _log(f"setColorTemperature error: {e}")
        return False


def _transition_to(new_state: str) -> None:
    """Transition to a new state, skipping if already in that state."""
    global _current_state

    if _current_state == new_state:
        _log(f"SKIP: already in state {new_state}")
        return

    old = _current_state
    _current_state = new_state
    _log(f"STATE CHANGE: {new_state} (was: {old})")

    if new_state == "THINKING":
        _set_color(hue=0, saturation=100, level=30)  # Red, dim
    elif new_state == "WAITING":
        _set_color(hue=70, saturation=100, level=50)  # Blue
    elif new_state == "IDLE":
        _set_color_temperature(temp=2700, level=20)  # Warm white, very dim


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
