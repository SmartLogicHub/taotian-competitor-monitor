import unittest

from taotian_price_tool.bi import (
    BiClient,
    BiImportConfig,
    BiTemplateItem,
    EarphoneGoodsFilter,
    extract_item_id,
    map_shop_to_brand,
    normalize_goods_link,
)


class FakeBiSession:
    def __init__(self):
        self.calls = []

    def request_json(self, endpoint, payload):
        self.calls.append((endpoint, payload))
        if endpoint.endswith("/shopTaskList"):
            return {
                "data": [
                    {"shopId": "xiaomi", "shopName": "小米官方旗舰店", "newCount": 3},
                    {"shopId": "soaiy", "shopName": "SOAIY旗舰店", "newCount": 1},
                    {"shopId": "edifier", "shopName": "漫步者官方旗舰店", "newCount": 1},
                ]
            }
        if payload["shopId"] == "xiaomi":
            return {
                "data": [
                    {
                        "goodsId": "1059057030771",
                        "goodsName": "Redmi Buds 6 入耳式降噪耳机",
                        "goodsLink": "http://a.m.taobao.com/i1059057030771.htm?&v=1.0&sid=2d87d4b9af39f6d0c80cb362595fdb4c&jose=1",
                        "goodsUrl": "https://img.alicdn.com/imgextra/i1/cover.jpg",
                        "cateName": "蓝牙耳机",
                        "catePathName": "影音电器>无线耳机",
                        "onSaleTime": "2026-06-20",
                        "price": "159",
                    },
                    {
                        "goodsId": "1059057030771",
                        "goodsName": "Redmi Buds 6 重复商品",
                        "goodsLink": "https://detail.tmall.com/item.htm?id=1059057030771",
                        "goodsUrl": "https://img.alicdn.com/imgextra/i1/duplicate.jpg",
                        "cateName": "蓝牙耳机",
                        "onSaleTime": "2026-06-20",
                    },
                    {
                        "goodsId": "999",
                        "goodsName": "小米空调",
                        "goodsLink": "https://detail.tmall.com/item.htm?id=999",
                        "cateName": "空调",
                    },
                ]
            }
        if payload["shopId"] == "soaiy":
            return {
                "data": [
                    {
                        "goodsId": "106",
                        "goodsName": "SOAIY 开放式耳夹耳机",
                        "goodsLink": "https://item.taobao.com/item.htm?id=106",
                        "cateName": "",
                        "catePathName": "",
                        "onSaleTime": "2026-06-19",
                    }
                ]
            }
        return {"data": []}


class DuplicateDateBiSession:
    def __init__(self, goods_rows):
        self.goods_rows = goods_rows

    def request_json(self, endpoint, payload):
        if endpoint.endswith("/shopTaskList"):
            return {"data": [{"shopId": "huazai", "shopName": "漫步者花再旗舰店", "newCount": len(self.goods_rows)}]}
        return {"data": list(self.goods_rows)}


class BiLinkTests(unittest.TestCase):
    def test_extracts_item_id_from_supported_taobao_and_noitem_links(self):
        self.assertEqual("1059057030771", extract_item_id("http://a.m.taobao.com/i1059057030771.htm?x=1"))
        self.assertEqual("1060464732667", extract_item_id("https://detail.tmall.com/item.htm?id=1060464732667"))
        self.assertEqual(
            "1060464732667",
            extract_item_id("https://error.item.taobao.com/error/noitem?type=noitem&itemid=1060464732667"),
        )

    def test_rejects_picture_urls_even_when_goods_url_exists(self):
        self.assertEqual("", normalize_goods_link({"goodsLink": "", "goodsUrl": "https://img.alicdn.com/a/b/c.jpg"}))
        self.assertEqual("", normalize_goods_link({"goodsLink": "https://img.alicdn.com/a/b/c.png", "goodsId": "1"}))

    def test_normalizes_goods_link_and_does_not_use_goods_url_picture(self):
        link = (
            "https://detail.tmall.com/item.htm?id=1059057030771&jose=1&sid=abc"
            "&v=1.0&sku_properties=5919063%3A6536025"
        )
        payload = {"goodsLink": link, "goodsUrl": "https://img.alicdn.com/a/b/c.jpg", "goodsId": "1059057030771"}

        self.assertEqual("https://detail.tmall.com/item.htm?id=1059057030771", normalize_goods_link(payload))

    def test_normalizes_mobile_goods_link_to_detail_short_link(self):
        payload = {
            "goodsLink": "http://a.m.taobao.com/i1059057030771.htm?&v=1.0&sid=abc&jose=1",
            "goodsUrl": "https://img.alicdn.com/a/b/c.jpg",
        }

        self.assertEqual("https://detail.tmall.com/item.htm?id=1059057030771", normalize_goods_link(payload))


class EarphoneFilterTests(unittest.TestCase):
    def test_keeps_category_or_title_that_indicates_earphone(self):
        goods_filter = EarphoneGoodsFilter()

        self.assertTrue(goods_filter.is_earphone({"cateName": "蓝牙耳机", "goodsName": "新品"}))
        self.assertTrue(goods_filter.is_earphone({"cateName": "", "goodsName": "SOAIY 开放式耳夹耳机"}))

    def test_rejects_explicit_non_earphone_goods(self):
        goods_filter = EarphoneGoodsFilter()

        self.assertFalse(goods_filter.is_earphone({"cateName": "手机", "goodsName": "小米手机"}))
        self.assertFalse(goods_filter.is_earphone({"cateName": "", "goodsName": "鼻毛修剪器"}))


    def test_rejects_speakers_and_generic_bluetooth_goods(self):
        goods_filter = EarphoneGoodsFilter()

        self.assertFalse(goods_filter.is_earphone({"cateName": "\u84dd\u7259\u97f3\u7bb1", "goodsName": "\u5c0f\u7c73\u84dd\u7259\u97f3\u7bb1"}))
        self.assertFalse(goods_filter.is_earphone({"cateName": "", "goodsName": "portable bluetooth speaker"}))
        self.assertFalse(goods_filter.is_earphone({"cateName": "", "goodsName": "home theater soundbar"}))
        self.assertFalse(goods_filter.is_earphone({"cateName": "", "goodsName": "\u84dd\u7259\u65b0\u54c1"}))
        self.assertFalse(goods_filter.is_earphone({"cateName": "\u84dd\u7259\u8033\u673a", "goodsName": "\u65b0\u54c1\u84dd\u7259\u97f3\u7bb1"}))

    def test_keeps_only_strong_earphone_signals_after_speaker_exclusion(self):
        goods_filter = EarphoneGoodsFilter()

        self.assertTrue(goods_filter.is_earphone({"cateName": "\u84dd\u7259\u8033\u673a", "goodsName": "\u65b0\u54c1"}))
        self.assertTrue(goods_filter.is_earphone({"cateName": "", "goodsName": "Redmi Buds 6"}))
        self.assertTrue(goods_filter.is_earphone({"cateName": "", "goodsName": "\u5934\u6234\u8033\u673a"}))


class BiClientTests(unittest.TestCase):
    def test_import_goods_maps_stores_filters_earphones_and_deduplicates_same_item_date(self):
        result = BiClient(session=FakeBiSession()).import_goods(
            BiImportConfig(start_date="2026-06-14", end_date="2026-06-20", days_type=7)
        )

        self.assertEqual(4, result.import_count)
        self.assertEqual(2, result.earphone_count)
        self.assertEqual(["小米", "索爱"], [item.brand for item in result.items])
        self.assertEqual("2026-06-20", result.items[0].on_sale_time)
        self.assertEqual(
            "https://detail.tmall.com/item.htm?id=1059057030771",
            result.items[0].goods_link,
        )
        self.assertEqual("https://detail.tmall.com/item.htm?id=1059057030771", result.items[0].fetch_link)
        self.assertEqual("Redmi Buds 6 入耳式降噪耳机", result.items[0].goods_name)
        self.assertNotIn("img.alicdn.com", result.items[0].goods_link)
        self.assertEqual("索爱", map_shop_to_brand("SOAIY旗舰店"))
        self.assertEqual("ikf", map_shop_to_brand("iKF旗舰店"))
        self.assertEqual("索爱麒麟专卖店", map_shop_to_brand("索爱麒麟专卖店"))
        self.assertEqual("雷蛇官方旗舰店", map_shop_to_brand("雷蛇官方旗舰店"))
        self.assertIsNone(map_shop_to_brand("漫步者官方旗舰店"))

    def test_non_earphone_new_goods_still_counts_brand_as_checked_not_earphone_new(self):
        rows = [
            {
                "goodsId": "88888888",
                "goodsName": "漫步者桌面音箱",
                "goodsLink": "https://detail.tmall.com/item.htm?id=88888888",
                "cateName": "音箱",
                "catePathName": "影音电器>音箱",
                "onSaleTime": "2026-06-20",
            }
        ]

        result = BiClient(session=DuplicateDateBiSession(rows)).import_goods(
            BiImportConfig(start_date="2026-06-14", end_date="2026-06-20", days_type=7),
            template_brands=["漫步者花再旗舰店"],
        )

        self.assertEqual(1, result.import_count)
        self.assertEqual(0, result.earphone_count)
        self.assertEqual(["漫步者花再旗舰店"], result.checked_brands)

    def test_import_goods_keeps_same_item_when_on_sale_date_differs(self):
        rows = [
            {
                "goodsId": "1052748824887",
                "goodsName": "漫步者花再Auro Ace蓝牙耳机小头戴式无线长续航运动久戴不痛新款",
                "goodsLink": "https://detail.tmall.com/item.htm?id=1052748824887",
                "cateName": "",
                "catePathName": "",
                "onSaleTime": "2026-06-18",
            },
            {
                "goodsId": "1052748824887",
                "goodsName": "漫步者花再Auro Ace蓝牙耳机小头戴式无线长续航运动久戴不痛新款",
                "goodsLink": "https://detail.tmall.com/item.htm?id=1052748824887",
                "cateName": "",
                "catePathName": "",
                "onSaleTime": "2026-06-14",
            },
        ]

        result = BiClient(session=DuplicateDateBiSession(rows)).import_goods(
            BiImportConfig(start_date="2026-06-14", end_date="2026-06-20", days_type=7),
            template_brands=["漫步者花再旗舰店"],
        )

        self.assertEqual(2, result.earphone_count)
        self.assertEqual(0, result.deduped_count)
        self.assertEqual(["2026-06-18", "2026-06-14"], [item.on_sale_time for item in result.items])
        self.assertEqual(
            ["https://detail.tmall.com/item.htm?id=1052748824887"] * 2,
            [item.goods_link for item in result.items],
        )

    def test_import_goods_deduplicates_same_shop_item_and_date(self):
        rows = [
            {
                "goodsId": "1052748824887",
                "goodsName": "漫步者花再Auro Ace蓝牙耳机小头戴式无线长续航运动久戴不痛新款",
                "goodsLink": "https://detail.tmall.com/item.htm?id=1052748824887",
                "cateName": "",
                "catePathName": "",
                "onSaleTime": "2026-06-18",
            },
            {
                "goodsId": "1052748824887",
                "goodsName": "漫步者花再Auro Ace蓝牙耳机小头戴式无线长续航运动久戴不痛新款",
                "goodsLink": "https://detail.tmall.com/item.htm?id=1052748824887",
                "cateName": "",
                "catePathName": "",
                "onSaleTime": "2026-06-18",
            },
        ]

        result = BiClient(session=DuplicateDateBiSession(rows)).import_goods(
            BiImportConfig(start_date="2026-06-14", end_date="2026-06-20", days_type=7),
            template_brands=["漫步者花再旗舰店"],
        )

        self.assertEqual(1, result.earphone_count)
        self.assertEqual(1, result.deduped_count)

    def test_template_item_date_is_formatted_for_existing_template_style(self):
        item = BiTemplateItem(
            brand="小米",
            shop_name="小米官方旗舰店",
            goods_name="Redmi Buds 6",
            goods_link="https://detail.tmall.com/item.htm?id=1",
            item_id="1",
            on_sale_time="2026-06-20",
        )

        self.assertEqual("6月20", item.display_date)


if __name__ == "__main__":
    unittest.main()
