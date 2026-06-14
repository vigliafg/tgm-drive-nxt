"""
Test per config.py — Gestione configurazione JSON.
"""

import json
from pathlib import Path

import pytest

from config import (
    load_config, save_config, ensure_config_dir,
    DEFAULT_CONFIG, CONFIG_DIR, CONFIG_FILE, SESSION_FILE
)


class TestDefaultConfig:
    """Test della configurazione di default."""

    def test_default_config_has_required_keys(self):
        """La configurazione di default deve contenere tutte le chiavi necessarie."""
        required = [
            "api_id", "api_hash", "phone", "channel_id", "channel_name",
            "download_dir", "ui_theme", "ui_font_size", "window_width",
            "window_height", "favorite_channels", "default_upload_channel_id",
        ]
        for key in required:
            assert key in DEFAULT_CONFIG, f"Manca la chiave '{key}' in DEFAULT_CONFIG"

    def test_default_config_values_are_valid(self):
        """I valori di default devono essere sensati."""
        assert DEFAULT_CONFIG["api_id"] == ""
        assert DEFAULT_CONFIG["api_hash"] == ""
        assert DEFAULT_CONFIG["phone"] == ""
        assert DEFAULT_CONFIG["channel_id"] == ""
        assert DEFAULT_CONFIG["ui_theme"] == "dark"
        assert DEFAULT_CONFIG["ui_font_size"] == 11
        assert DEFAULT_CONFIG["window_width"] == 1200
        assert DEFAULT_CONFIG["window_height"] == 700
        assert isinstance(DEFAULT_CONFIG["favorite_channels"], list)
        assert DEFAULT_CONFIG["default_upload_channel_id"] is None

    def test_config_dir_is_in_home(self):
        """La directory di configurazione deve essere nella home dell'utente."""
        assert str(CONFIG_DIR).endswith(".tgm_drive")


class TestLoadAndSaveConfig:
    """Test di caricamento e salvataggio configurazione."""

    def test_load_config_returns_defaults_when_no_file(self, monkeypatch, tmp_path):
        """Se non esiste il file di config, restituisce i default."""
        monkeypatch.setattr("config.CONFIG_FILE", tmp_path / "nonexistent.json")
        monkeypatch.setattr("config.CONFIG_DIR", tmp_path)
        config = load_config()
        # Deve contenere almeno tutte le chiavi di default
        for key in DEFAULT_CONFIG:
            assert key in config

    def test_load_config_merges_with_defaults(self, monkeypatch, tmp_path):
        """Il caricamento deve fare merge tra file e DEFAULT_CONFIG."""
        config_dir = tmp_path / ".tgm_drive"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.json"
        partial_config = {"api_id": "99999", "ui_theme": "light"}
        config_file.write_text(json.dumps(partial_config), encoding="utf-8")

        monkeypatch.setattr("config.CONFIG_FILE", config_file)
        monkeypatch.setattr("config.CONFIG_DIR", config_dir)

        config = load_config()
        assert config["api_id"] == "99999"
        assert config["ui_theme"] == "light"
        # Le altre chiavi vengono dai default
        assert config["ui_font_size"] == 11
        assert config["phone"] == ""

    def test_save_and_reload_config(self, monkeypatch, tmp_path):
        """Salva una configurazione e verifica che venga ricaricata identica."""
        config_dir = tmp_path / ".tgm_drive"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.json"

        monkeypatch.setattr("config.CONFIG_FILE", config_file)
        monkeypatch.setattr("config.CONFIG_DIR", config_dir)

        test_config = DEFAULT_CONFIG.copy()
        test_config["api_id"] = "12345"
        test_config["api_hash"] = "abcdef"
        test_config["phone"] = "+391234567890"
        test_config["channel_id"] = "-1001234567890"
        test_config["ui_theme"] = "system"

        save_config(test_config)
        loaded = load_config()

        assert loaded["api_id"] == "12345"
        assert loaded["api_hash"] == "abcdef"
        assert loaded["phone"] == "+391234567890"
        assert loaded["channel_id"] == "-1001234567890"
        assert loaded["ui_theme"] == "system"

    def test_save_config_creates_directory(self, monkeypatch, tmp_path):
        """Il salvataggio deve creare la directory se non esiste."""
        config_dir = tmp_path / ".tgm_drive"
        config_file = config_dir / "config.json"

        monkeypatch.setattr("config.CONFIG_FILE", config_file)
        monkeypatch.setattr("config.CONFIG_DIR", config_dir)

        assert not config_dir.exists()
        save_config(DEFAULT_CONFIG.copy())
        assert config_dir.exists()
        assert config_file.exists()

    def test_save_config_is_valid_json(self, monkeypatch, tmp_path):
        """Il file salvato deve essere JSON valido."""
        config_dir = tmp_path / ".tgm_drive"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.json"

        monkeypatch.setattr("config.CONFIG_FILE", config_file)
        monkeypatch.setattr("config.CONFIG_DIR", config_dir)

        save_config(DEFAULT_CONFIG.copy())

        with open(config_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert isinstance(data, dict)
        for key in DEFAULT_CONFIG:
            assert key in data

    def test_load_config_preserves_unknown_keys(self, monkeypatch, tmp_path):
        """Chiavi sconosciute nel file devono essere preservate (forward compat)."""
        config_dir = tmp_path / ".tgm_drive"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.json"
        extra_config = {"api_id": "111", "future_feature": "enabled"}
        config_file.write_text(json.dumps(extra_config), encoding="utf-8")

        monkeypatch.setattr("config.CONFIG_FILE", config_file)
        monkeypatch.setattr("config.CONFIG_DIR", config_dir)

        config = load_config()
        assert config["future_feature"] == "enabled"
        assert config["api_id"] == "111"

    def test_ensure_config_dir_creates_download_dir(self, monkeypatch, tmp_path):
        """ensure_config_dir deve creare anche la cartella download."""
        config_dir = tmp_path / ".tgm_drive"
        download_dir = tmp_path / "downloads_test"

        monkeypatch.setattr("config.CONFIG_DIR", config_dir)
        # Modifica DEFAULT_CONFIG localmente per puntare al tmp_path
        original_dl = DEFAULT_CONFIG["download_dir"]
        DEFAULT_CONFIG["download_dir"] = str(download_dir)
        try:
            ensure_config_dir()
            assert config_dir.exists()
            assert download_dir.exists()
        finally:
            DEFAULT_CONFIG["download_dir"] = original_dl


class TestSessionFile:
    """Test del percorso del file di sessione."""

    def test_session_file_is_in_config_dir(self):
        """Il file di sessione deve essere nella cartella .tgm_drive."""
        assert str(SESSION_FILE.parent) == str(CONFIG_DIR)
        assert SESSION_FILE.name == "tgm_drive"
