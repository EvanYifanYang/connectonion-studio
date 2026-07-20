"""Regression tests for Studio's per-agent trust compatibility layer."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from connectonion.network.trust import tools as framework_trust_tools
from connectonion.network.trust.trust_agent import TrustAgent

from co_studio import creator
from co_studio.runner import co_studio_runner
from co_studio.scoped_trust import ScopedTrustAgent, scope_host


INVITE_POLICY = """---
allow: [whitelisted, contact]
deny: [blocked]
onboard:
  invite_code: [agent-code]
default: deny
---
Only invited clients may connect.
"""


class ScopedTrustAgentTests(unittest.TestCase):
    def test_global_framework_contact_does_not_authorize_scoped_agent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            global_dir = root / "global"
            global_dir.mkdir()
            (global_dir / "contacts.txt").write_text("0xclient\n")

            with patch.object(framework_trust_tools, "CO_DIR", global_dir):
                trust = ScopedTrustAgent(INVITE_POLICY, co_dir=root / "agent" / ".co")
                decision = trust.should_allow("0xclient")

            self.assertFalse(decision.allow)
            self.assertEqual(trust.get_level("0xclient"), "stranger")

    def test_invite_promotion_is_visible_only_to_the_target_agent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = ScopedTrustAgent(INVITE_POLICY, co_dir=root / "first" / ".co")
            second = ScopedTrustAgent(INVITE_POLICY, co_dir=root / "second" / ".co")

            self.assertTrue(first.verify_invite("0xclient", "agent-code"))

            self.assertTrue(first.should_allow("0xclient").allow)
            self.assertFalse(second.should_allow("0xclient").allow)
            self.assertEqual((root / "first" / ".co" / "contacts.txt").read_text(), "0xclient\n")
            self.assertFalse((root / "second" / ".co" / "contacts.txt").exists())

    def test_direct_invite_request_and_blocklist_stay_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trust = ScopedTrustAgent(INVITE_POLICY, co_dir=root / ".co")

            admitted = trust.should_allow("0xclient", {"invite_code": "agent-code"})
            trust.block("0xclient", "test")

            self.assertTrue(admitted.allow)
            self.assertFalse(trust.should_allow("0xclient").allow)
            self.assertEqual(trust.get_level("0xclient"), "blocked")

    def test_open_policy_keeps_allowing_unknown_clients(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trust = ScopedTrustAgent("open", co_dir=Path(tmp) / ".co")
            self.assertTrue(trust.should_allow("0xstranger").allow)


class ScopedHostTests(unittest.TestCase):
    def test_wrapper_replaces_string_policy_with_framework_compatible_instance(self) -> None:
        captured = {}

        def fake_host(agent, *args, **kwargs):
            captured.update(agent=agent, args=args, kwargs=kwargs)
            return "hosted"

        with tempfile.TemporaryDirectory() as tmp:
            co_dir = Path(tmp) / ".co"
            result = scope_host(fake_host)(
                "agent", port=8000, trust=INVITE_POLICY, co_dir=co_dir
            )

        scoped = captured["kwargs"]["trust"]
        self.assertEqual(result, "hosted")
        self.assertIsInstance(scoped, ScopedTrustAgent)
        self.assertIsInstance(scoped, TrustAgent)
        self.assertEqual(scoped.co_dir, co_dir.resolve())

    def test_wrapper_preserves_explicit_custom_trust_agent(self) -> None:
        captured = {}

        def fake_host(_agent, **kwargs):
            captured.update(kwargs)

        custom = TrustAgent("open")
        scope_host(fake_host)("agent", trust=custom, co_dir=Path(".co"))

        self.assertIs(captured["trust"], custom)

    def test_runner_path_covers_both_generated_templates(self) -> None:
        custom = creator.render("Custom", creator.DEFAULT_MODEL, 8000, [], "open")
        co_ai = creator.render(
            "Coder", creator.DEFAULT_MODEL, 8001, [], "strict", preset="co-ai", invite_code="code"
        )

        self.assertIn("from connectonion import Agent, host", custom)
        self.assertIn("from connectonion import host", co_ai)
        self.assertIn("host(create_agent,", custom)
        self.assertIn("host(agent,", co_ai)

    def test_runner_installs_wrapper_on_connectonion_public_host(self) -> None:
        import connectonion

        def fake_host(_agent, **_kwargs):
            return None

        with patch.object(connectonion, "host", fake_host):
            co_studio_runner._patch_scoped_trust()
            self.assertTrue(connectonion.host._co_studio_scoped_trust)


if __name__ == "__main__":
    unittest.main()
