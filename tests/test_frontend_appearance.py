"""Static contract for Warm-default and Lavender appearance behavior."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "co_studio/frontend/index.html").read_text()
JS = (ROOT / "co_studio/frontend/js/app.js").read_text()
API_JS = (ROOT / "co_studio/frontend/js/api.js").read_text()
THEME = (ROOT / "co_studio/frontend/css/theme.css").read_text()
APPEARANCE = (ROOT / "co_studio/frontend/css/appearance.css").read_text()
MAC_APP = (
    ROOT / "macos/ConnectOnionStudio/ConnectOnionStudio/ConnectOnionStudioApp.swift"
).read_text()
MAC_WEBVIEW = (
    ROOT / "macos/ConnectOnionStudio/ConnectOnionStudio/WebView.swift"
).read_text()
DIAGNOSTICS = (ROOT / "co_studio/frontend/js/diagnostics.js").read_text()


class AppearanceContractTests(unittest.TestCase):
    def test_warm_is_the_prepaint_and_runtime_default(self) -> None:
        self.assertIn("const serverAppearance = '__CO_STUDIO_APPEARANCE__';", HTML)
        self.assertIn("initialAppearance = 'warm'", HTML)
        self.assertIn("window.__coStudioInitialAppearance", JS)
        self.assertRegex(
            HTML,
            r'name="appearance" value="warm" checked',
        )
        self.assertNotRegex(
            HTML,
            r'name="appearance" value="lavender" checked',
        )

    def test_warm_and_lavender_keep_separate_harmonious_accents(self) -> None:
        self.assertIn("--accent:      #9A5B3A;", THEME)
        lavender = re.search(
            r':root\[data-appearance="lavender"\]\s*\{(?P<body>.*?)\n\}',
            APPEARANCE,
            re.DOTALL,
        )
        self.assertIsNotNone(lavender)
        self.assertIn("--accent:      #6E56F2;", lavender.group("body"))
        self.assertIn(':root[data-appearance="lavender"] .btn-primary', APPEARANCE)

    def test_choice_persists_outside_port_scoped_browser_storage(self) -> None:
        self.assertIn("api.setAppearance(appearance)", JS)
        self.assertIn("'/api/settings/appearance'", API_JS)
        self.assertIn("window.__coStudio?.setAppearance?.(appearance)", JS)
        self.assertIn('.appendingPathComponent(".co-studio/config.json")', MAC_APP)
        self.assertIn("StartingView(appearance: appearance)", MAC_APP)
        self.assertIn("appearance.canvasNSColor", MAC_WEBVIEW)
        self.assertIn("setAppearance: function (appearance)", MAC_WEBVIEW)

    def test_native_clipboard_and_reopen_skip_the_welcome_animation(self) -> None:
        self.assertIn("window.__coStudio?.copyText", DIAGNOSTICS)
        self.assertIn("copyText: function (text)", MAC_WEBVIEW)
        self.assertIn('case "copyText"', MAC_WEBVIEW)
        self.assertIn("window.__coStudioSkipSplash", MAC_WEBVIEW)
        self.assertIn("window.__coStudioSkipSplash === true", JS)


if __name__ == "__main__":
    unittest.main()
