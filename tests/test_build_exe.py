import tempfile
import unittest
from pathlib import Path

from taotian_price_tool.build_exe import build_commands_for_variant


class BuildExeTests(unittest.TestCase):
    def test_full_variant_includes_bundled_chromium_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            chromium = Path(tmp) / "chromium-1223" / "chrome-win64"
            chromium.mkdir(parents=True)
            (chromium / "chrome.exe").write_text("", encoding="utf-8")

            commands = build_commands_for_variant("full", ms_playwright_root=Path(tmp))

        self.assertEqual(1, len(commands))
        command = commands[0]
        self.assertIn("--add-data", command)
        self.assertIn("dist_v10_dedupe_browser_full", command)
        self.assertTrue(any("chromium-1223" in part for part in command))

    def test_lite_variant_omits_bundled_chromium_data(self):
        commands = build_commands_for_variant("lite", ms_playwright_root=Path("unused"))

        self.assertEqual(1, len(commands))
        command = commands[0]
        self.assertNotIn("--add-data", command)
        self.assertIn("dist_v10_dedupe_browser_lite", command)

    def test_both_variant_builds_full_then_lite(self):
        with tempfile.TemporaryDirectory() as tmp:
            chromium = Path(tmp) / "chromium-1223" / "chrome-win64"
            chromium.mkdir(parents=True)
            (chromium / "chrome.exe").write_text("", encoding="utf-8")

            commands = build_commands_for_variant("both", ms_playwright_root=Path(tmp))

        self.assertEqual(2, len(commands))
        self.assertIn("dist_v10_dedupe_browser_full", commands[0])
        self.assertIn("dist_v10_dedupe_browser_lite", commands[1])


if __name__ == "__main__":
    unittest.main()
