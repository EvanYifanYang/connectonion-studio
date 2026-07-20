"""Static contract tests for the Template-aware create wizard."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "co_studio/frontend/index.html").read_text()
JS = (ROOT / "co_studio/frontend/js/app.js").read_text()


class CoAiWizardContractTests(unittest.TestCase):
    def test_template_is_between_name_and_model(self) -> None:
        self.assertLess(HTML.index('id="f-name"'), HTML.index('id="f-template"'))
        self.assertLess(HTML.index('id="f-template"'), HTML.index('id="f-model"'))

    def test_co_ai_access_has_invite_code_and_no_toolkit_step(self) -> None:
        self.assertIn('value="co-ai"', HTML)
        self.assertIn('id="f-invite-code"', HTML)
        self.assertIn("isCoAiTemplate() ? [0, 1, 2, 4]", JS)
        self.assertIn("$('#create-toolkit-step').hidden = coAi", JS)

    def test_create_payload_includes_preset_and_invite_code(self) -> None:
        self.assertIn(
            "api.createAgent({ name, model, toolkits, trust, preset, invite_code })",
            JS,
        )


if __name__ == "__main__":
    unittest.main()
