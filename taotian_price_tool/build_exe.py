from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys


APP_NAME = "淘天竞品监控工作台"
PLAYWRIGHT_BROWSER_DEST = "playwright/driver/package/.local-browsers"
FULL_DIST = "dist_v10_dedupe_browser_full"
LITE_DIST = "dist_v10_dedupe_browser_lite"
FULL_BUILD = "build_v10_dedupe_browser_full"
LITE_BUILD = "build_v10_dedupe_browser_lite"


def default_ms_playwright_root() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "ms-playwright"
    return Path.home() / "AppData" / "Local" / "ms-playwright"


def find_latest_chromium(ms_playwright_root: Path) -> Path:
    candidates: list[tuple[int, Path]] = []
    for path in Path(ms_playwright_root).glob("chromium-*"):
        if not path.is_dir():
            continue
        try:
            revision = int(path.name.split("-", 1)[1])
        except (IndexError, ValueError):
            continue
        chrome_exe = path / "chrome-win64" / "chrome.exe"
        if chrome_exe.exists():
            candidates.append((revision, path))
    if not candidates:
        raise FileNotFoundError(
            f"没有在 {ms_playwright_root} 找到可打包的 chromium-* 浏览器目录；请先运行 python -m playwright install chromium"
        )
    return max(candidates, key=lambda item: item[0])[1]


def _base_pyinstaller_command(*, dist_path: str, work_path: str) -> list[str]:
    return [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--noconsole",
        "--distpath",
        dist_path,
        "--workpath",
        work_path,
        "--specpath",
        work_path,
        "--name",
        APP_NAME,
        "--collect-all",
        "playwright",
        "--collect-all",
        "cryptography",
        "run_app.py",
    ]


def build_pyinstaller_command(*, variant: str = "full", ms_playwright_root: Path | None = None) -> list[str]:
    if variant not in {"full", "lite"}:
        raise ValueError("variant must be 'full' or 'lite'")
    if variant == "lite":
        return _base_pyinstaller_command(dist_path=LITE_DIST, work_path=LITE_BUILD)

    root = ms_playwright_root or default_ms_playwright_root()
    chromium = find_latest_chromium(root)
    add_data = f"{chromium}{os.pathsep}{PLAYWRIGHT_BROWSER_DEST}/{chromium.name}"
    command = _base_pyinstaller_command(dist_path=FULL_DIST, work_path=FULL_BUILD)
    insert_at = command.index("run_app.py")
    command[insert_at:insert_at] = ["--add-data", add_data]
    return command


def build_commands_for_variant(variant: str, *, ms_playwright_root: Path | None = None) -> list[list[str]]:
    if variant == "both":
        return [
            build_pyinstaller_command(variant="full", ms_playwright_root=ms_playwright_root),
            build_pyinstaller_command(variant="lite", ms_playwright_root=ms_playwright_root),
        ]
    if variant in {"full", "lite"}:
        return [build_pyinstaller_command(variant=variant, ms_playwright_root=ms_playwright_root)]
    raise ValueError("variant must be one of: full, lite, both")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build Taotian workbench executables")
    parser.add_argument("--variant", choices=["full", "lite", "both"], default="both")
    args = parser.parse_args(argv)

    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    if args.variant in {"full", "both"}:
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
    for command in build_commands_for_variant(args.variant):
        if "--add-data" in command:
            print("PyInstaller add-data: " + command[command.index("--add-data") + 1])
        else:
            print("PyInstaller add-data: <none, system Chrome/Edge required>")
        Path(command[command.index("--workpath") + 1]).mkdir(parents=True, exist_ok=True)
        subprocess.check_call(command)
    print(f"Build complete: {args.variant}")


if __name__ == "__main__":
    main()
