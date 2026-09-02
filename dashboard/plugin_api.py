from fastapi import APIRouter
import datetime
import json
import os
import urllib.request

router = APIRouter()
LOG_FILE = os.environ.get("LIGHT_ON_LLM_DESKTOP_LOG_FILE", "/tmp/light_on_llm_desktop.log")


def _log(msg: str) -> None:
    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(LOG_FILE, 'a') as f:
        f.write(f"{ts} - [desktop-api] {msg}\n")


HUE_BRIDGE_URL = os.environ.get("HUE_BRIDGE_URL", "http://YOUR-HUE-BRIDGE-IP").rstrip("/")
HUE_API_KEY = os.environ.get("HUE_API_KEY", "")
HUE_LIGHT_ID = os.environ.get("HUE_LIGHT_ID", "")

THINKING_LOCAL_XY = [0.6915, 0.3083]
THINKING_CLOUD_HUE = 50000
IDLE_XY = [0.2098, 0.5407]
THINKING_BRI = 25
IDLE_BRI = 5


def _hue_light_url() -> str:
    return f"{HUE_BRIDGE_URL}/api/{HUE_API_KEY}/lights/{HUE_LIGHT_ID}/state"


def _require_hue_config() -> str | None:
    if not HUE_API_KEY or not HUE_LIGHT_ID:
        msg = "HUE_API_KEY and HUE_LIGHT_ID are required for desktop light updates"
        _log(msg)
        return msg
    return None


def _put_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method="PUT",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=3) as resp:
        body = resp.read()
        return {
            "status": getattr(resp, "status", 200),
            "data": json.loads(body) if body else {},
        }


@router.post("/set-light")
async def set_light(body: dict) -> dict:
    _log(f"API request received: POST /set-light body={body}")

    cfg_error = _require_hue_config()
    if cfg_error:
        return {"success": False, "error": cfg_error}

    state = body.get("state", "IDLE")
    is_cloud = body.get("isCloud", True)

    try:
        if state == "THINKING":
            if is_cloud:
                result = _put_json(
                    _hue_light_url(),
                    {"hue": THINKING_CLOUD_HUE, "sat": 255, "bri": THINKING_BRI, "on": True},
                )
            else:
                result = _put_json(
                    _hue_light_url(),
                    {"xy": THINKING_LOCAL_XY, "bri": THINKING_BRI, "on": True},
                )
        elif state == "IDLE":
            result = _put_json(
                _hue_light_url(),
                {"xy": IDLE_XY, "bri": IDLE_BRI, "on": True},
            )
        else:
            return {"success": False, "error": f"Unknown state {state}"}

        _log(f"Hue API success: status={result['status']}")
        return {"success": True, "data": result["data"]}
    except Exception as e:
        _log(f"Hue API error: {e}")
        return {"success": False, "error": str(e)}
