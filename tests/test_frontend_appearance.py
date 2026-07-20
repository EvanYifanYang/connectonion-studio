"""Static contract for Warm-default and Lavender appearance behavior."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "co_studio/frontend/index.html").read_text()
JS = (ROOT / "co_studio/frontend/js/app.js").read_text()
THEME = (ROOT / "co_studio/frontend/css/theme.css").read_text()
APPEARANCE = (ROOT / "co_studio/frontend/css/appearance.css").read_text()


class AppearanceContractTests(unittest.TestCase):
    def test_warm_is_the_prepaint_and_runtime_default(self) -> None:
        self.assertIn("localStorage.getItem('co-studio-appearance') || 'warm'", HTML)
        self.assertIn("let saved = 'warm';", JS)
        self.assertIn("localStorage.getItem(APPEARANCE_KEY) || 'warm'", JS)
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


if __name__ == "__main__":
    unittest.main()
