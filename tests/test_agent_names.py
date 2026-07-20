"""Agent display-name uniqueness across create and rename surfaces."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from co_studio import config, creator, registry
from co_studio.api.agents import RenameBody, rename_agent
from co_studio.registry import AgentMeta


def _meta(slug: str, name: str, port: int) -> AgentMeta:
    return AgentMeta(
        slug=slug,
        name=name,
        address=f"0x{slug}",
        port=port,
        model=creator.DEFAULT_MODEL,
        capabilities=["utility"],
        created_at=f"2026-07-20T00:00:0{port - 8000}+00:00",
    )


class AgentRenameNameTests(unittest.TestCase):
    def _seed(self, root: Path) -> tuple[Path, AgentMeta, AgentMeta]:
        agents_dir = root / "agents"
        first = _meta("alpha", "Alpha Agent", 8000)
        second = _meta("beta", "Beta Agent", 8001)
        for meta in (first, second):
            agent_dir = agents_dir / meta.slug
            agent_dir.mkdir(parents=True)
            registry.save(meta)
            (agent_dir / "agent.py").write_text(f"# {meta.name}\n")
        return agents_dir, first, second

    def test_rename_rejects_another_agents_normalized_name_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with (
                patch.object(config, "AGENTS_DIR", root / "agents"),
                patch.object(config, "INDEX_LOCK", root / "index.lock"),
            ):
                agents_dir, first, _second = self._seed(root)
                original_script = (agents_dir / first.slug / "agent.py").read_text()

                with self.assertRaises(HTTPException) as raised:
                    rename_agent(first.slug, RenameBody(name=" beta-agent "))

                self.assertEqual(raised.exception.status_code, 409)
                self.assertEqual(raised.exception.detail, "An agent with that name already exists.")
                self.assertEqual(registry.load(first.slug).name, "Alpha Agent")
                self.assertEqual((agents_dir / first.slug / "agent.py").read_text(), original_script)

    def test_rename_allows_keeping_own_normalized_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with (
                patch.object(config, "AGENTS_DIR", root / "agents"),
                patch.object(config, "INDEX_LOCK", root / "index.lock"),
            ):
                self._seed(root)
                result = rename_agent("alpha", RenameBody(name="Alpha-Agent"))

                self.assertEqual(result["name"], "Alpha-Agent")
                self.assertEqual(registry.load("alpha").name, "Alpha-Agent")


class FrontendRenameNameContractTests(unittest.TestCase):
    def test_inline_rename_reuses_name_validation_and_bottom_toast(self) -> None:
        app_js = (
            Path(__file__).resolve().parents[1] / "co_studio/frontend/js/app.js"
        ).read_text()

        self.assertIn("const validation = nameStatus(name, agent.slug);", app_js)
        self.assertIn("toast(validation.msg, 'danger');", app_js)
        self.assertIn("a.slug !== excludeSlug && slugify(a.name) === slug", app_js)
        self.assertIn("toast(err.status === 409 ? err.message", app_js)


if __name__ == "__main__":
    unittest.main()
