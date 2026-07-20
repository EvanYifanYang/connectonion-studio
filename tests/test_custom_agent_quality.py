"""Regression tests for Custom Agent prompt quality and context compaction."""

from __future__ import annotations

import unittest

from co_studio import creator


class CustomAgentQualityTests(unittest.TestCase):
    def test_system_prompt_has_style_accuracy_and_tool_contracts(self) -> None:
        prompt = creator._system_prompt("Research Helper", ["utility", "web"])

        self.assertIn("You are Research Helper", prompt)
        self.assertIn("fetching web pages", prompt)
        self.assertIn("## Response style", prompt)
        self.assertIn("## Accuracy", prompt)
        self.assertIn("## Tool use", prompt)
        self.assertIn("Do not claim a tool action succeeded", prompt)
        self.assertNotIn("coding agent", prompt.lower())

    def test_no_tool_selection_still_describes_plain_conversation(self) -> None:
        self.assertIn("Available capabilities: plain conversation", creator._system_prompt("Chat", []))

    def test_custom_template_registers_auto_compact(self) -> None:
        rendered = creator.render(
            "Helper",
            creator.DEFAULT_MODEL,
            8000,
            ["utility"],
            "open",
        )

        self.assertIn("from connectonion.useful_plugins import auto_compact", rendered)
        self.assertIn("plugins = [*plugins, auto_compact]", rendered)
        self.assertIn("plugins=plugins", rendered)
        compile(rendered, "agent.py", "exec")

    def test_co_ai_template_keeps_framework_managed_plugin_set(self) -> None:
        rendered = creator.render(
            "Coder",
            creator.DEFAULT_MODEL,
            8001,
            [],
            "strict",
            preset="co-ai",
            invite_code="quality-test",
        )

        self.assertNotIn("plugins = [*plugins, auto_compact]", rendered)
        self.assertIn("create_coding_agent", rendered)


if __name__ == "__main__":
    unittest.main()
