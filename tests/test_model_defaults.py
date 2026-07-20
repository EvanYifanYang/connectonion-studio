"""Contracts for Studio's default model across API and both wizard modes."""

from __future__ import annotations

import unittest
from pathlib import Path

from co_studio import creator
from co_studio.api.agents import CreateAgentBody


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "co_studio/frontend/index.html").read_text()
JS = (ROOT / "co_studio/frontend/js/app.js").read_text()


class ModelDefaultTests(unittest.TestCase):
    def test_api_and_creator_default_to_gemini_35_flash(self) -> None:
        self.assertEqual(creator.DEFAULT_MODEL, "co/gemini-3.5-flash")
        self.assertEqual(CreateAgentBody(name="Helper").model, creator.DEFAULT_MODEL)

    def test_html_select_marks_only_gemini_35_as_default(self) -> None:
        self.assertIn(
            '<option value="co/gemini-3.5-flash" selected>'
            'co/gemini-3.5-flash — managed key (default)</option>',
            HTML,
        )
        self.assertIn(
            '<option value="co/gemini-2.5-flash">'
            'co/gemini-2.5-flash — managed key</option>',
            HTML,
        )

    def test_create_modal_reset_uses_same_default_for_both_modes(self) -> None:
        self.assertIn("$('#f-model').value = 'co/gemini-3.5-flash';", JS)
        self.assertNotIn(
            "coAi ? 'co/gemini-3.5-flash' : 'co/gemini-2.5-flash'",
            JS,
        )


if __name__ == "__main__":
    unittest.main()
