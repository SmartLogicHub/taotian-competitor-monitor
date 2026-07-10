import unittest

from taotian_price_tool.safety import (
    CrawlIntensity,
    SafetyController,
    SafetyDecision,
)


class SafetyControllerTests(unittest.TestCase):
    def test_conservative_intensity_uses_slow_default_delay_window(self):
        intensity = CrawlIntensity.conservative()

        self.assertEqual(8, intensity.min_delay_seconds)
        self.assertEqual(20, intensity.max_delay_seconds)
        self.assertEqual("保守", intensity.label)

    def test_two_consecutive_verifications_pause_the_batch(self):
        controller = SafetyController()

        first = controller.record_result(row=2, status="needs_verification")
        second = controller.record_result(row=3, status="needs_verification")

        self.assertEqual(SafetyDecision.CONTINUE, first.decision)
        self.assertEqual(SafetyDecision.PAUSE, second.decision)
        self.assertIn("连续 2 次", second.reason)

    def test_failure_rate_above_twenty_percent_pauses_after_minimum_sample(self):
        controller = SafetyController(min_rows_for_failure_rate=5)

        for row, status in [
            (2, "success"),
            (3, "success"),
            (4, "success"),
            (5, "failed"),
        ]:
            controller.record_result(row=row, status=status)
        result = controller.record_result(row=6, status="failed")

        self.assertEqual(SafetyDecision.PAUSE, result.decision)
        self.assertIn("失败率", result.reason)

    def test_manual_confirmation_intensity_has_no_auto_delay(self):
        intensity = CrawlIntensity.manual_confirmation()

        self.assertEqual(0, intensity.min_delay_seconds)
        self.assertEqual(0, intensity.max_delay_seconds)
        self.assertTrue(intensity.requires_confirmation)

    def test_ultra_conservative_intensity_uses_slowest_delay_window(self):
        intensity = CrawlIntensity.ultra_conservative()

        self.assertEqual(45, intensity.min_delay_seconds)
        self.assertEqual(90, intensity.max_delay_seconds)
        self.assertEqual("超保守", intensity.label)


if __name__ == "__main__":
    unittest.main()
