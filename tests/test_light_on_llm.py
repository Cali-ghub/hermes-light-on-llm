# pyright: reportAttributeAccessIssue=false
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_PATH = ROOT / "__init__.py"


def load_plugin(**env):
    old_env = os.environ.copy()
    os.environ.clear()
    os.environ.update(old_env)
    os.environ.update({
        "LIGHT_ON_LLM_LOG_FILE": tempfile.mktemp(prefix="light-on-llm-test-", suffix=".log"),
        **env,
    })
    spec = importlib.util.spec_from_file_location("light_on_llm_under_test", PLUGIN_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    module._DEBOUNCE_SECS = 0
    return module


class FakeResponse:
    status = 200

    def read(self):
        return b'[{"success":{"/lights/1/state/on":true}}]'


class LightOnLlmTests(unittest.TestCase):
    def test_model_and_platform_color_selection(self):
        plugin = load_plugin()

        self.assertEqual(plugin._light_spec("THINKING", model="model.gguf")[0], "red")
        self.assertEqual(plugin._light_spec("THINKING", model="openrouter/example")[0], "purple")
        self.assertEqual(plugin._light_spec("THINKING", model="model.gguf", platform="cron")[0], "cron")
        self.assertEqual(plugin._light_spec("WAITING")[0], "blue")
        self.assertEqual(plugin._light_spec("IDLE")[0], "green")

    def test_hubitat_set_color_builds_valid_maker_api_url(self):
        plugin = load_plugin(LIGHT_BACKEND="hubitat")
        plugin.HUBITAT_BASE = "http://hub/apps/api/277/devices/613"
        plugin.ACCESS_TOKEN = "TOKEN"
        seen = []

        def fake_urlopen(url, timeout=5):
            seen.append(url)
            return FakeResponse()

        with patch("urllib.request.urlopen", fake_urlopen):
            self.assertTrue(plugin._hubitat_set_color(hue=80, saturation=100, level=10))

        self.assertEqual(len(seen), 1)
        self.assertIn("/setColor/%7B%22hue%22%3A80%2C%22saturation%22%3A100%2C%22level%22%3A10%7D?access_token=TOKEN", seen[0])
        self.assertNotIn("%7D&access_token", seen[0])

    def test_hubitat_cloud_color_uses_hubitat_scale_purple(self):
        plugin = load_plugin(LIGHT_BACKEND="hubitat")
        plugin.BACKEND = "hubitat"
        plugin.ACCESS_TOKEN = "TOKEN"
        plugin.HUBITAT_BASE = "http://hub/apps/api/277/devices/613"
        calls = []

        def fake_set_color(hue, saturation, level):
            calls.append((hue, saturation, level))
            return True

        plugin._hubitat_set_color = fake_set_color
        self.assertTrue(plugin._set_light("THINKING", model="openrouter/example"))
        self.assertEqual(calls, [(80, 100, 10)])

    def test_failed_backend_call_does_not_cache_color(self):
        plugin = load_plugin(LIGHT_BACKEND="hue", HUE_API_KEY="KEY", HUE_LIGHT_ID="1")
        plugin.BACKEND = "hue"
        plugin._last_light_color = None
        plugin._hue_set_xy = lambda xy, bri_byte: False

        self.assertFalse(plugin._set_light("IDLE"))
        self.assertIsNone(plugin._last_light_color)

    def test_successful_backend_call_caches_color(self):
        plugin = load_plugin(LIGHT_BACKEND="hue", HUE_API_KEY="KEY", HUE_LIGHT_ID="1")
        plugin.BACKEND = "hue"
        plugin._last_light_color = None
        plugin._hue_set_xy = lambda xy, bri_byte: True

        self.assertTrue(plugin._set_light("IDLE"))
        self.assertEqual(plugin._last_light_color, "green")


if __name__ == "__main__":
    unittest.main()
