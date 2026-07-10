import unittest

from taotian_price_tool.classifier import ALLOWED_SHAPES, HeuristicShapeClassifier, normalize_shape


class HeuristicShapeClassifierTests(unittest.TestCase):
    def test_classifies_to_six_standard_shapes(self):
        classifier = HeuristicShapeClassifier()

        examples = {
            "AirPods 4 半入耳 蓝牙耳机": "半入耳",
            "Redmi Buds 6 真无线入耳式降噪耳机": "入耳式",
            "开放式耳夹蓝牙耳机 不入耳": "耳夹式",
            "Sony WH-1000XM5 头戴式无线降噪耳机": "头戴式",
            "运动挂脖式蓝牙耳机 长续航": "挂脖式",
            "骨传导挂耳式开放式蓝牙耳机": "挂耳式",
        }

        for title, expected in examples.items():
            with self.subTest(title=title):
                self.assertEqual(expected, classifier.classify(title).shape)

    def test_unclear_title_defaults_to_allowed_shape_without_unknown(self):
        result = HeuristicShapeClassifier().classify("蓝牙耳机 新款 高清音质")

        self.assertIn(result.shape, ALLOWED_SHAPES)
        self.assertNotIn(result.shape, {"待确认", "未知"})

    def test_normalize_shape_maps_legacy_or_ai_output_to_standard_shapes(self):
        self.assertEqual("入耳式", normalize_shape("真无线入耳式"))
        self.assertEqual("半入耳", normalize_shape("真无线半入耳式"))
        self.assertEqual("耳夹式", normalize_shape("开放式/耳夹式"))
        self.assertEqual("挂耳式", normalize_shape("骨传导/开放式"))
        self.assertEqual("入耳式", normalize_shape("待确认"))


if __name__ == "__main__":
    unittest.main()
