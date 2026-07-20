"""Static contracts for the native single-window application lifecycle."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = (
    ROOT / "macos/ConnectOnionStudio/ConnectOnionStudio/ConnectOnionStudioApp.swift"
).read_text()
SERVER = (
    ROOT / "macos/ConnectOnionStudio/ConnectOnionStudio/StudioServer.swift"
).read_text()
WEBVIEW = (
    ROOT / "macos/ConnectOnionStudio/ConnectOnionStudio/WebView.swift"
).read_text()


class MacWindowLifecycleContractTests(unittest.TestCase):
    def test_close_keeps_app_alive_and_dock_reopens_retained_window(self) -> None:
        self.assertIn("applicationShouldTerminateAfterLastWindowClosed", APP)
        self.assertIn("-> Bool { false }", APP)
        self.assertIn("applicationShouldHandleReopen", APP)
        self.assertIn("window.isReleasedWhenClosed = false", APP)

    def test_explicit_quit_always_tears_down_the_server_promptly(self) -> None:
        self.assertIn("applicationWillTerminate", APP)
        self.assertIn("StudioServer.shared.shutdownForQuit()", APP)
        self.assertIn("private static let quitGrace: TimeInterval = 0.5", SERVER)
        self.assertIn("if proc.isRunning { kill(proc.processIdentifier, SIGKILL) }", SERVER)

    def test_only_a_cold_process_launch_plays_the_welcome_animation(self) -> None:
        self.assertIn("NativeLaunchPresentation.hasLoadedInitialPage", WEBVIEW)
        self.assertIn("window.__coStudioSkipSplash", WEBVIEW)


if __name__ == "__main__":
    unittest.main()
