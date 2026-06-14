import os
import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".tgm_drive"
CONFIG_FILE = CONFIG_DIR / "config.json"
SESSION_FILE = CONFIG_DIR / "tgm_drive"

DEFAULT_CONFIG = {
    "api_id": "",
    "api_hash": "",
    "phone": "",
    "channel_id": "",
    "channel_name": "TGM Drive Cloud",
    "download_dir": str(Path.home() / "TGM_Drive_Downloads"),
    "ui_theme": "dark",
    "ui_font_size": 11,
    "window_width": 1200,
    "window_height": 700,
    "favorite_channels": [],
    "default_upload_channel_id": None,
}


def ensure_config_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    download_dir = Path(DEFAULT_CONFIG["download_dir"])
    download_dir.mkdir(parents=True, exist_ok=True)


def load_config():
    ensure_config_dir()
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return {**DEFAULT_CONFIG, **json.load(f)}
    return DEFAULT_CONFIG.copy()


def save_config(config: dict):
    ensure_config_dir()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
