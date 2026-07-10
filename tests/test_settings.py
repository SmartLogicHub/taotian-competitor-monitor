import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from taotian_price_tool.feishu_config import load_feishu_credentials, save_feishu_credentials
from taotian_price_tool.settings import SettingsStore


class SettingsStoreTests(unittest.TestCase):
    def test_load_continues_when_saved_secret_cannot_be_decrypted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            path.write_text(
                json.dumps({"deepseek_api_key": "dpapi:broken", "intensity": "标准"}, ensure_ascii=False),
                encoding="utf-8",
            )

            with patch("taotian_price_tool.settings.unprotect_secret", side_effect=OSError("cannot decrypt")):
                settings = SettingsStore(path).load()

            self.assertEqual("", settings.deepseek_api_key)
            self.assertEqual("标准", settings.intensity)

    def test_feishu_credentials_persist_selected_table_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("taotian_price_tool.feishu_config.app_data_dir", return_value=Path(tmp)):
                save_feishu_credentials(
                    "cli_saved",
                    "secret_saved",
                    "https://example.feishu.cn/base/base_token",
                    table_id="tbl_sop",
                    table_name="上新sop",
                )

                loaded = load_feishu_credentials()

            self.assertEqual("cli_saved", loaded["app_id"])
            self.assertEqual("secret_saved", loaded["app_secret"])
            self.assertEqual("https://example.feishu.cn/base/base_token", loaded["app_token"])
            self.assertEqual("tbl_sop", loaded["table_id"])
            self.assertEqual("上新sop", loaded["table_name"])


if __name__ == "__main__":
    unittest.main()
