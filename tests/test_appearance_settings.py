"""Studio-wide appearance persistence independent of the manager's port."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from co_studio import config
from co_studio.api.settings_api import AppearanceBody, get_appearance, set_appearance
from co_studio.app import create_app


class AppearanceSettingsTests(unittest.TestCase):
    def _config_patches(self, root: Path):
        return (
            patch.object(config, "STUDIO_HOME", root),
            patch.object(config, "SETTINGS_FILE", root / "config.json"),
            patch.object(config, "SETTINGS_LOCK", root / "config.lock"),
        )

    def test_appearance_survives_restart_and_preserves_other_settings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            patches = self._config_patches(root)
            with patches[0], patches[1], patches[2]:
                config.save_agents_dir(root / "agents")
                set_appearance(AppearanceBody(appearance="lavender"))

                self.assertEqual(get_appearance(), {"appearance": "lavender"})
                saved = json.loads((root / "config.json").read_text())

            self.assertEqual(saved["agents_dir"], str(root / "agents"))
            self.assertEqual(saved["appearance"], "lavender")

    def test_invalid_appearance_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            patches = self._config_patches(root)
            with patches[0], patches[1], patches[2]:
                with self.assertRaises(HTTPException) as raised:
                    set_appearance(AppearanceBody(appearance="neon"))
            self.assertEqual(raised.exception.status_code, 422)

    def test_index_injects_saved_appearance_before_first_paint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            frontend = root / "frontend"
            frontend.mkdir()
            (frontend / "index.html").write_text(
                "<script>const appearance = '__CO_STUDIO_APPEARANCE__';</script>"
            )
            patches = self._config_patches(root)
            with (
                patches[0], patches[1], patches[2],
                patch.object(config, "FRONTEND_DIR", frontend),
            ):
                config.save_appearance("lavender")
                app = create_app()
                index_route = next(route for route in app.routes if getattr(route, "path", None) == "/")
                response = index_route.endpoint()

            self.assertIn("const appearance = 'lavender';", response.body.decode())


if __name__ == "__main__":
    unittest.main()
