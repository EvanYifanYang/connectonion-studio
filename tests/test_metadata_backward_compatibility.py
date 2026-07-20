"""Bidirectional Agent metadata compatibility for upgrades and rollbacks."""

from __future__ import annotations

import dataclasses
import json
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

from co_studio import config, registry
from co_studio.registry import AgentMeta


def _current_meta(slug: str = "modern") -> AgentMeta:
    return AgentMeta(
        slug=slug,
        name="Modern",
        address="0xmodern",
        port=8000,
        model="co/gemini-3.5-flash",
        capabilities=["utility", "web"],
        created_at="2026-07-20T00:00:00+00:00",
        preset="custom",
        invite_code=None,
    )


@dataclass
class _OldAgentMeta:
    """The metadata shape required by the already-installed legacy app."""

    slug: str
    name: str
    address: str
    port: int
    model: str
    toolkits: list[str]
    created_at: str
    trust: str = "open"


class MetadataBackwardCompatibilityTests(unittest.TestCase):
    def _patch_registry(self, root: Path):
        return (
            patch.object(config, "AGENTS_DIR", root / "agents"),
            patch.object(config, "INDEX_LOCK", root / "index.lock"),
        )

    def test_current_save_writes_fields_both_versions_can_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            patches = self._patch_registry(root)
            with patches[0], patches[1]:
                agent_dir = config.AGENTS_DIR / "modern"
                agent_dir.mkdir(parents=True)
                registry.save(_current_meta())
                data = json.loads((agent_dir / "meta.json").read_text())

            self.assertEqual(data["capabilities"], ["utility", "web"])
            self.assertEqual(data["toolkits"], data["capabilities"])
            old_fields = {field.name for field in dataclasses.fields(_OldAgentMeta)}
            old_meta = _OldAgentMeta(**{key: value for key, value in data.items() if key in old_fields})
            self.assertEqual(old_meta.toolkits, ["utility", "web"])

    def test_startup_migration_is_bidirectional_and_preserves_new_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            patches = self._patch_registry(root)
            with patches[0], patches[1]:
                old_dir = config.AGENTS_DIR / "old"
                new_dir = config.AGENTS_DIR / "new"
                old_dir.mkdir(parents=True)
                new_dir.mkdir(parents=True)
                (old_dir / "meta.json").write_text(json.dumps({
                    "slug": "old", "toolkits": ["utility"], "future": "keep-me",
                }))
                (new_dir / "meta.json").write_text(json.dumps({
                    "slug": "new", "capabilities": ["utility", "shell"],
                    "preset": "co-ai", "invite_code": "secret-code",
                }))

                migrated = registry.migrate_capability_aliases()
                old_data = json.loads((old_dir / "meta.json").read_text())
                new_data = json.loads((new_dir / "meta.json").read_text())

            self.assertEqual(migrated, 2)
            self.assertEqual(old_data["capabilities"], old_data["toolkits"])
            self.assertEqual(old_data["future"], "keep-me")
            self.assertEqual(new_data["toolkits"], new_data["capabilities"])
            self.assertEqual(new_data["preset"], "co-ai")
            self.assertEqual(new_data["invite_code"], "secret-code")

    def test_current_capabilities_win_when_aliases_disagree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            patches = self._patch_registry(root)
            with patches[0], patches[1]:
                agent_dir = config.AGENTS_DIR / "conflict"
                agent_dir.mkdir(parents=True)
                (agent_dir / "meta.json").write_text(json.dumps({
                    "capabilities": ["utility", "browser"],
                    "toolkits": ["utility"],
                }))
                self.assertEqual(registry.migrate_capability_aliases(), 1)
                data = json.loads((agent_dir / "meta.json").read_text())

            self.assertEqual(data["toolkits"], ["utility", "browser"])

    def test_migration_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            patches = self._patch_registry(root)
            with patches[0], patches[1]:
                agent_dir = config.AGENTS_DIR / "modern"
                agent_dir.mkdir(parents=True)
                registry.save(_current_meta())
                self.assertEqual(registry.migrate_capability_aliases(), 0)


if __name__ == "__main__":
    unittest.main()
