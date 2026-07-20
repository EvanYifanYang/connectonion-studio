"""Per-agent workspace metadata and sandbox escape regressions."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from co_studio import config, creator, registry, workspaces
from co_studio.sandbox import SandboxedBrowserPaths, SandboxedFileTools, SandboxedShell


class WorkspaceCreationTests(unittest.TestCase):
    def test_default_workspace_is_private_and_moves_with_agent_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agents_dir = root / "agents"
            with (
                patch.object(config, "AGENTS_DIR", agents_dir),
                patch.object(config, "INDEX_LOCK", root / "index.lock"),
                patch.object(config, "KEYS_ENV", root / "missing-keys.env"),
                patch.object(creator.identity, "create", return_value="0xworkspace"),
                patch.object(creator.ports, "allocate", return_value=8000),
            ):
                meta = creator.create("Workspace", creator.DEFAULT_MODEL, ["utility"])
                first = workspaces.effective_work_dir(meta)
                config.AGENTS_DIR = root / "moved-agents"
                second = workspaces.effective_work_dir(meta)

            self.assertIsNone(meta.work_dir)
            self.assertTrue(first.is_dir())
            self.assertEqual(first, (agents_dir / "workspace" / "workspace").resolve())
            self.assertEqual(second, (root / "moved-agents" / "workspace" / "workspace").resolve())

    def test_explicit_workspace_must_be_an_existing_absolute_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agents_dir = root / "agents"
            project = root / "project"
            project.mkdir()
            with patch.object(config, "AGENTS_DIR", agents_dir):
                path, stored = workspaces.prepare("coder", str(project), require_write=True)
                with self.assertRaisesRegex(ValueError, "absolute"):
                    workspaces.prepare("coder", "relative/project", require_write=False)
                with self.assertRaisesRegex(ValueError, "does not exist"):
                    workspaces.prepare("coder", str(root / "missing"), require_write=False)
            self.assertEqual(path, project.resolve())
            self.assertEqual(stored, str(project.resolve()))

    def test_generated_co_ai_configures_workspace_before_building_agent(self) -> None:
        rendered = creator.render(
            "Coder", creator.DEFAULT_MODEL, 8000, [], "strict",
            preset="co-ai", invite_code="workspace-code", work_dir="/tmp/project",
        )
        self.assertIn("WORK_DIR_VALUE = '/tmp/project'", rendered)
        self.assertLess(
            rendered.index("configure_process_environment(WORK_DIR, RUNTIME_DIR)"),
            rendered.index("agent = create_coding_agent"),
        )
        self.assertIn("sandbox_coding_agent(agent, WORK_DIR, RUNTIME_DIR)", rendered)
        compile(rendered, "agent.py", "exec")

    def test_old_metadata_without_workspace_still_loads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            agents_dir = Path(tmp)
            directory = agents_dir / "old"
            directory.mkdir()
            (directory / "meta.json").write_text(json.dumps({
                "slug": "old", "name": "Old", "address": "0xold", "port": 8000,
                "model": creator.DEFAULT_MODEL, "toolkits": ["utility"],
                "created_at": "2026-07-20T00:00:00+00:00",
            }))
            with patch.object(config, "AGENTS_DIR", agents_dir):
                meta = registry.load("old")
                self.assertIsNone(meta.work_dir)
                self.assertEqual(workspaces.effective_work_dir(meta), (directory / "workspace").resolve())


class FileSandboxTests(unittest.TestCase):
    def test_files_allow_workspace_and_reject_absolute_traversal_and_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            outside = root / "outside"
            workspace.mkdir()
            outside.mkdir()
            secret = outside / "secret.txt"
            secret.write_text("DO-NOT-LEAK")
            (workspace / "escape").symlink_to(outside, target_is_directory=True)

            files = SandboxedFileTools(workspace)
            self.assertIn("Successfully wrote", files.write("inside.txt", "safe"))
            self.assertIn("safe", files.read_file("inside.txt"))
            for result in (
                files.read_file(str(secret)),
                files.read_file("../outside/secret.txt"),
                files.read_file("escape/secret.txt"),
                files.write("escape/new.txt", "blocked"),
                files.glob("../**/*"),
            ):
                self.assertIn("Workspace access denied", result)
            self.assertFalse((outside / "new.txt").exists())


class BrowserPathSandboxTests(unittest.TestCase):
    def test_browser_rejects_local_urls_and_paths_outside_workspace(self) -> None:
        class BrowserStub:
            def go_to(self, url, purpose="", who="", hours=0.0): return url
            def run_page_script(self, path, args_json="{}"): return path
            def save_state(self, path): return path
            def upload_file_by_selector(self, selector, path, *args): return path

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            outside = root / "outside.js"
            workspace.mkdir()
            inside = workspace / "inside.js"
            inside.write_text("1")
            outside.write_text("2")
            browser = SandboxedBrowserPaths(BrowserStub(), workspace)

            self.assertEqual(browser.run_page_script("inside.js"), str(inside.resolve()))
            self.assertIn("Workspace access denied", browser.go_to(outside.as_uri()))
            self.assertIn("Workspace access denied", browser.run_page_script(str(outside)))
            self.assertIn("Workspace access denied", browser.save_state(str(root / "state.json")))
            self.assertIn(
                "Workspace access denied",
                browser.upload_file_by_selector("input", str(outside)),
            )


@unittest.skipUnless(sys.platform == "darwin", "Seatbelt workspace sandbox is macOS-only")
class ShellSandboxTests(unittest.TestCase):
    def test_shell_can_work_inside_but_cannot_read_or_write_outside(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            runtime = root / "runtime"
            outside = root / "outside"
            workspace.mkdir()
            outside.mkdir()
            secret = outside / "secret.txt"
            secret.write_text("DO-NOT-LEAK")
            shell = SandboxedShell(workspace, runtime)

            inside = shell.bash("printf safe > inside.txt && cat inside.txt", "inside write")
            escaped_read = shell.bash(f"cat {secret}", "outside read")
            escaped_write = shell.bash(f"printf bad > {outside / 'new.txt'}", "outside write")
            bad_cwd = shell.bash("pwd", "outside cwd", cwd="../outside")

            self.assertIn("safe", inside)
            self.assertNotIn("DO-NOT-LEAK", escaped_read)
            self.assertIn("Operation not permitted", escaped_read)
            self.assertIn("Operation not permitted", escaped_write)
            self.assertFalse((outside / "new.txt").exists())
            self.assertIn("Workspace access denied", bad_cwd)


if __name__ == "__main__":
    unittest.main()
