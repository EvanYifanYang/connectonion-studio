"""Static UI contract for risk-tiered Custom Agent capabilities."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "co_studio/frontend/index.html").read_text()
JS = (ROOT / "co_studio/frontend/js/app.js").read_text()
CSS = (ROOT / "co_studio/frontend/css/app.css").read_text()


class CapabilityWizardContractTests(unittest.TestCase):
    def test_capability_catalog_shows_all_risk_groups(self) -> None:
        self.assertIn("<h3>Capabilities</h3>", HTML)
        for capability in ("web", "image", "files", "file-write", "shell", "browser"):
            self.assertIn(f'name="capability" value="{capability}"', HTML)
        for level in ("public", "private", "powerful"):
            self.assertIn(f'data-risk="{level}"', HTML)
            self.assertIn(f"is-{level}", HTML)
        self.assertIn(".capability-legend", CSS)
        self.assertNotIn(">Strict</span>", HTML)
        self.assertNotIn(">Invite</span>", HTML)

    def test_custom_access_is_derived_and_invite_is_conditional(self) -> None:
        self.assertNotIn('name="trust"', HTML)
        self.assertIn('id="f-custom-invite-code"', HTML)
        self.assertIn("function customAccessPolicy()", JS)
        self.assertIn("policy.tier > 0 ? $('#f-custom-invite-code').value.trim() : null", JS)
        self.assertIn("const trust = coAi ? 'strict' : policy.trust", JS)
        self.assertIn("title: 'Invite-only access'", JS)
        self.assertIn("badge: 'Invite only'", JS)
        self.assertIn("Approval is remembered for this device and this Agent only.", JS)
        self.assertIn("function accessLabel(agent)", JS)
        self.assertIn("$('.access-val', card).textContent = accessLabel(agent)", JS)
        self.assertIn("['Access', accessLabel(detail)]", JS)

    def test_file_read_and_write_choices_do_not_duplicate_tools(self) -> None:
        self.assertIn("checkbox.value === 'file-write'", JS)
        self.assertIn("checkbox.value === 'files'", JS)

    def test_details_use_new_field_with_legacy_fallback(self) -> None:
        self.assertIn("detail.capabilities || detail.toolkits || []", JS)
        self.assertIn("agent.capabilities || agent.toolkits || []", JS)


if __name__ == "__main__":
    unittest.main()
