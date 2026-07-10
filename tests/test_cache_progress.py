import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from taotian_price_tool.cache import DailyResultCache
from taotian_price_tool.progress import TaskProgressStore


class CacheAndProgressTests(unittest.TestCase):
    def test_cache_reuses_same_url_on_same_day_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = DailyResultCache(Path(tmp) / "cache.json")
            cache.set(
                "https://detail.tmall.com/item.htm?id=1",
                {"price": "159", "shape": "真无线入耳式"},
                today=date(2026, 6, 20),
            )

            same_day = cache.get(
                "https://detail.tmall.com/item.htm?id=1",
                today=date(2026, 6, 20),
            )
            next_day = cache.get(
                "https://detail.tmall.com/item.htm?id=1",
                today=date(2026, 6, 21),
            )

            self.assertEqual("159", same_day["price"])
            self.assertIsNone(next_day)

    def test_progress_store_persists_each_row_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "progress.json"
            store = TaskProgressStore(path)

            store.record_row(
                source_file="input.xlsx",
                row=7,
                url="https://item.taobao.com/item.htm?id=7",
                status="success",
                price="88",
                shape="开放式/耳夹式",
                note="ok",
            )

            payload = json.loads(path.read_text(encoding="utf-8"))
            loaded = TaskProgressStore(path).load()

            self.assertEqual("input.xlsx", payload["source_file"])
            self.assertEqual("success", loaded.rows["7"].status)
            self.assertEqual("88", loaded.rows["7"].price)


if __name__ == "__main__":
    unittest.main()
