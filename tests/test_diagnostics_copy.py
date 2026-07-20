"""Copy button feedback should stay compact so its layout never jumps."""

from __future__ import annotations

import unittest
from pathlib import Path


SOURCE = (
    Path(__file__).resolve().parents[1]
    / "co_studio/frontend/js/diagnostics.js"
).read_text()


class DiagnosticsCopyContractTests(unittest.TestCase):
    def test_copy_feedback_uses_compact_labels(self) -> None:
        self.assertIn("flash(btn, ok ? 'Copied' : 'Clipboard blocked');", SOURCE)
        self.assertNotIn("paste into Claude", SOURCE)
        self.assertNotIn("copy manually", SOURCE)


if __name__ == "__main__":
    unittest.main()
