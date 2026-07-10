from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import random


class SafetyDecision(str, Enum):
    CONTINUE = "continue"
    PAUSE = "pause"


@dataclass(frozen=True)
class CrawlIntensity:
    label: str
    min_delay_seconds: int
    max_delay_seconds: int
    requires_confirmation: bool = False

    @classmethod
    def conservative(cls) -> "CrawlIntensity":
        return cls("保守", 8, 20)

    @classmethod
    def standard(cls) -> "CrawlIntensity":
        return cls("标准", 5, 12)

    @classmethod
    def manual_confirmation(cls) -> "CrawlIntensity":
        return cls("手动确认", 0, 0, True)

    @classmethod
    def account_protection(cls) -> "CrawlIntensity":
        return cls("账号保护", 20, 40)

    @classmethod
    def ultra_conservative(cls) -> "CrawlIntensity":
        return cls("超保守", 45, 90)

    def next_delay_seconds(self) -> int:
        if self.min_delay_seconds == self.max_delay_seconds:
            return self.min_delay_seconds
        return random.randint(self.min_delay_seconds, self.max_delay_seconds)


@dataclass(frozen=True)
class SafetyResult:
    decision: SafetyDecision
    reason: str = ""


class SafetyController:
    verification_statuses = {"needs_verification", "login_required", "captcha"}
    failure_statuses = {"failed", "error", "needs_verification", "login_required", "captcha"}

    def __init__(
        self,
        *,
        consecutive_verification_limit: int = 2,
        failure_rate_limit: float = 0.20,
        min_rows_for_failure_rate: int = 10,
    ) -> None:
        self.consecutive_verification_limit = consecutive_verification_limit
        self.failure_rate_limit = failure_rate_limit
        self.min_rows_for_failure_rate = min_rows_for_failure_rate
        self.total_rows = 0
        self.failed_rows = 0
        self.consecutive_verifications = 0

    def record_result(self, *, row: int, status: str) -> SafetyResult:
        self.total_rows += 1
        if status in self.failure_statuses:
            self.failed_rows += 1

        if status in self.verification_statuses:
            self.consecutive_verifications += 1
        else:
            self.consecutive_verifications = 0

        if self.consecutive_verifications >= self.consecutive_verification_limit:
            return SafetyResult(
                SafetyDecision.PAUSE,
                f"连续 {self.consecutive_verifications} 次出现登录/验证/异常页，已暂停在第 {row} 行。",
            )

        if self.total_rows >= self.min_rows_for_failure_rate:
            failure_rate = self.failed_rows / self.total_rows
            if failure_rate > self.failure_rate_limit:
                return SafetyResult(
                    SafetyDecision.PAUSE,
                    f"当前批次失败率 {failure_rate:.0%}，超过 20%，已暂停。",
                )

        return SafetyResult(SafetyDecision.CONTINUE)
