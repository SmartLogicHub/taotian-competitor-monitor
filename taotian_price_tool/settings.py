from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import json
import os
from pathlib import Path


def app_data_dir() -> Path:
    root = os.environ.get("APPDATA")
    if root:
        return Path(root) / "TaotianPriceTool"
    return Path.home() / ".taotian_price_tool"


@dataclass
class AppSettings:
    deepseek_api_key: str = ""
    intensity: str = "超保守"
    output_dir: str = ""


class SettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or app_data_dir() / "settings.json"

    def load(self) -> AppSettings:
        if not self.path.exists():
            return AppSettings(deepseek_api_key=os.environ.get("DEEPSEEK_API_KEY", ""))
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return AppSettings()
        try:
            deepseek_api_key = unprotect_secret(payload.get("deepseek_api_key", ""))
        except Exception:
            deepseek_api_key = ""
        return AppSettings(
            deepseek_api_key=deepseek_api_key,
            intensity=payload.get("intensity", "超保守"),
            output_dir=str(payload.get("output_dir", "")).strip(),
        )

    def save(self, settings: AppSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "deepseek_api_key": protect_secret(settings.deepseek_api_key),
            "intensity": settings.intensity,
            "output_dir": settings.output_dir,
        }
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def protect_secret(secret: str) -> str:
    if not secret:
        return ""
    if os.name != "nt":
        return "plain:" + base64.b64encode(secret.encode("utf-8")).decode("ascii")
    return "dpapi:" + _crypt_protect(secret.encode("utf-8"))


def unprotect_secret(value: str) -> str:
    if not value:
        return ""
    if value.startswith("plain:"):
        return base64.b64decode(value[6:].encode("ascii")).decode("utf-8")
    if value.startswith("dpapi:") and os.name == "nt":
        return _crypt_unprotect(value[6:]).decode("utf-8")
    return ""


class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    ]


def _crypt_protect(data: bytes) -> str:
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    in_blob = DATA_BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data), ctypes.POINTER(ctypes.c_char)))
    out_blob = DATA_BLOB()
    if not crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    ):
        raise ctypes.WinError()
    try:
        protected = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        return base64.b64encode(protected).decode("ascii")
    finally:
        kernel32.LocalFree(out_blob.pbData)


def _crypt_unprotect(value: str) -> bytes:
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    protected = base64.b64decode(value.encode("ascii"))
    in_blob = DATA_BLOB(
        len(protected),
        ctypes.cast(ctypes.create_string_buffer(protected), ctypes.POINTER(ctypes.c_char)),
    )
    out_blob = DATA_BLOB()
    if not crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)
