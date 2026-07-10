"""飞书凭证加密存储"""
from __future__ import annotations

import json
import os
from pathlib import Path

from cryptography.fernet import Fernet

from .settings import app_data_dir


def _config_dir() -> Path:
    return app_data_dir() / "feishu_config"


def _ensure_dir() -> None:
    _config_dir().mkdir(parents=True, exist_ok=True)


def _get_cipher() -> Fernet:
    _ensure_dir()
    key_file = _config_dir() / ".key"
    if key_file.exists():
        key = key_file.read_bytes()
    else:
        key = Fernet.generate_key()
        key_file.write_bytes(key)
    return Fernet(key)


def save_feishu_credentials(
    app_id: str,
    app_secret: str,
    app_token: str = "",
    *,
    table_id: str = "",
    table_name: str = "",
) -> None:
    cipher = _get_cipher()
    data = json.dumps({
        "app_id": app_id,
        "app_secret": app_secret,
        "app_token": app_token,
        "table_id": table_id,
        "table_name": table_name,
    }).encode()
    encrypted = cipher.encrypt(data)
    (_config_dir() / "config.enc").write_bytes(encrypted)


def load_feishu_credentials() -> dict | None:
    config_file = _config_dir() / "config.enc"
    if not config_file.exists():
        return None
    cipher = _get_cipher()
    encrypted = config_file.read_bytes()
    try:
        data = cipher.decrypt(encrypted)
        return json.loads(data.decode())
    except Exception:
        return None


def clear_feishu_credentials() -> None:
    config_file = _config_dir() / "config.enc"
    key_file = _config_dir() / ".key"
    if config_file.exists():
        config_file.unlink()
    if key_file.exists():
        key_file.unlink()
