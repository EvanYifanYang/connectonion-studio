"""Static UI contract for risk-tiered Custom Agent capabilities."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "co_studio/frontend/index.html").read_text()
JS = (ROOT / "co_studio/frontend/js/app.js").read_text()
CSS = (ROOT / "co_studio/frontend/css/app.css").read_text()


class CapabilityWizardContractTests(unittest.TestCase):
    def test_capability_catalog_shows_standard_and_protected_groups(self) -> None:
        self.assertIn("<h3>Capabilities</h3>", HTML)
        for capability in ("web", "image", "files", "file-write", "shell", "browser"):
            self.assertIn(f'name="capability" value="{capability}"', HTML)
        self.assertNotIn('class="capability-legend"', HTML)
        self.assertNotIn(".capability-legend", CSS)
        self.assertNotIn('class="capability-access-tag"', HTML)
        self.assertEqual(HTML.count('class="capability-group"'), 2)
        self.assertIn('<b>Standard</b><small>- Invite code optional</small>', HTML)
        self.assertIn('<b>Protected</b><small>- Invite code required</small>', HTML)
        self.assertEqual(HTML.count('class="toolkit-option" data-access="optional"'), 2)
        self.assertEqual(HTML.count('class="toolkit-option" data-access="required"'), 4)
        self.assertIn('.toolkit-option[data-access="optional"] .tk-ico', CSS)
        self.assertIn('.toolkit-option[data-access="required"] .tk-ico', CSS)
        self.assertIn(".toolkits-grid .toolkit-option small { white-space: nowrap", CSS)
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr))", CSS)
        self.assertIn(".toolkits-grid .toolkit-option { min-width: 0;", CSS)
        self.assertNotIn(">Strict</span>", HTML)
        self.assertNotIn(">Invite</span>", HTML)

    def test_custom_access_is_derived_and_invite_is_conditional(self) -> None:
        self.assertNotIn('name="trust"', HTML)
        self.assertIn('name="standard-access" value="open" checked', HTML)
        self.assertIn('name="standard-access" value="invite"', HTML)
        self.assertIn('id="f-custom-invite-code"', HTML)
        self.assertNotIn('value="developer"', HTML)
        self.assertEqual(HTML.count('placeholder="Create an invite code"'), 2)
        self.assertIn("function customAccessPolicy()", JS)
        self.assertIn("policy.inviteOnly ? $('#f-custom-invite-code').value.trim() : null", JS)
        self.assertIn("const trust = coAi ? 'strict' : policy.trust", JS)
        self.assertIn("function inviteCodeError(code)", JS)
        self.assertIn("Create an invite code before continuing.", JS)
        self.assertIn("title: 'Invite-only access'", JS)
        self.assertIn("badge: 'Invite only'", JS)
        self.assertEqual(JS.count("copy: 'New devices enter your code once.'"), 2)
        self.assertIn("policy.tier === 0 ? 'is-safe' : 'is-strict'", JS)
        self.assertIn('.capability-access[data-risk="careful"],', CSS)
        self.assertIn('.risk-badge.is-strict { color: var(--danger); background: var(--elevated); }', CSS)
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
