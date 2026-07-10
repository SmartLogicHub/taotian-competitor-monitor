import unittest

from taotian_price_tool.classifier import ALLOWED_SHAPES
from taotian_price_tool.deepseek import DeepSeekShapeClassifier


class FakeTransport:
    def __init__(self, response=None, exc=None):
        self.response = response or {}
        self.exc = exc
        self.requests = []

    def post_json(self, url, headers, payload):
        self.requests.append((url, headers, payload))
        if self.exc:
            raise self.exc
        return self.response


class DeepSeekShapeClassifierTests(unittest.TestCase):
    def test_without_api_key_falls_back_to_standard_heuristic_classifier(self):
        classifier = DeepSeekShapeClassifier(api_key="", transport=FakeTransport({}))

        result = classifier.classify("开放式耳夹蓝牙耳机")

        self.assertEqual("耳夹式", result.shape)

    def test_with_api_key_requests_json_shape_output_and_normalizes_result(self):
        transport = FakeTransport(
            {
                "choices": [
                    {
                        "message": {
                            "content": '{"shape":"真无线半入耳式","reason":"标题包含半入耳"}'
                        }
                    }
                ]
            }
        )
        classifier = DeepSeekShapeClassifier(api_key="sk-test", transport=transport)

        result = classifier.classify("AirPods 半入耳真无线蓝牙耳机")

        self.assertEqual("半入耳", result.shape)
        _url, headers, payload = transport.requests[0]
        self.assertEqual("Bearer sk-test", headers["Authorization"])
        self.assertEqual({"type": "json_object"}, payload["response_format"])
        self.assertEqual("deepseek-v4-flash", payload["model"])
        system_prompt = payload["messages"][0]["content"]
        for shape in ALLOWED_SHAPES:
            self.assertIn(shape, system_prompt)
        self.assertNotIn("待确认", system_prompt)

    def test_deepseek_failure_falls_back_without_unknown_shape(self):
        classifier = DeepSeekShapeClassifier(api_key="sk-test", transport=FakeTransport(exc=RuntimeError("boom")))

        result = classifier.classify("蓝牙耳机 新款 高清音质")

        self.assertIn(result.shape, ALLOWED_SHAPES)
        self.assertNotIn(result.shape, {"待确认", "未知"})


if __name__ == "__main__":
    unittest.main()
