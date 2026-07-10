from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable


DEFAULT_BROWSER_CHANNELS: tuple[str | None, ...] = ("chrome", "msedge", None)


class BrowserLaunchError(RuntimeError):
    pass


def _source_name(channel: str | None) -> str:
    return channel or "bundled_chromium"


def launch_persistent_context_with_fallback(
    browser_type: Any,
    *,
    user_data_dir: str | Path,
    headless: bool,
    viewport: dict[str, int],
    locale: str,
    args: list[str],
    preferred_channels: Iterable[str | None] = DEFAULT_BROWSER_CHANNELS,
    allow_bundled: bool = True,
) -> tuple[Any, str]:
    attempts: list[str] = []
    errors: list[str] = []
    for channel in preferred_channels:
        if channel is None and not allow_bundled:
            continue
        source = _source_name(channel)
        attempts.append(source)
        options: dict[str, Any] = {
            "user_data_dir": str(user_data_dir),
            "headless": headless,
            "viewport": viewport,
            "locale": locale,
            "args": args,
        }
        if channel is not None:
            options["channel"] = channel
        try:
            return browser_type.launch_persistent_context(**options), source
        except Exception as exc:
            errors.append(f"{source}: {exc}")

    attempted = "、".join(attempts) if attempts else "无"
    detail = "；".join(errors)
    raise BrowserLaunchError(
        f"未找到可用浏览器（已尝试 {attempted}）。请安装 Chrome/Edge 或使用 full 版。{detail}"
    )
