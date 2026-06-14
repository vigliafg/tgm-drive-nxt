"""
Test per auth_dialog.py — AuthDialog: credenziali API Telegram.

Testa validazione campi (API ID, Hash, Phone), caricamento/salvataggio
configurazione, e pulsanti Salva/Annulla.
"""

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox

from gui.auth_dialog import AuthDialog


# ─── Fixture ──────────────────────────────────────────────────────────

@pytest.fixture
def dialog(temp_config, qtbot):
    """AuthDialog con config di test."""
    dlg = AuthDialog(temp_config)
    qtbot.addWidget(dlg)
    return dlg


# ─── Inizializzazione ──────────────────────────────────────────────────

class TestAuthDialogInit:
    """Test dello stato iniziale."""

    def test_window_title(self, dialog):
        assert dialog.windowTitle() == "TGM Drive - Autenticazione Telegram"

    def test_minimum_width(self, dialog):
        assert dialog.minimumWidth() == 400

    def test_placeholders(self, dialog):
        assert dialog.api_id_edit.placeholderText() == "12345"
        assert dialog.api_hash_edit.placeholderText() == "abc123..."
        assert dialog.phone_edit.placeholderText() == "+39333..."

    def test_has_save_and_cancel_buttons(self, dialog):
        assert dialog.action_btn.text() == "Salva"
        assert dialog.cancel_btn.text() == "Annulla"

    def test_save_button_is_default(self, dialog):
        assert dialog.action_btn.isDefault()

    def test_info_label_has_link(self, dialog):
        """Il label info contiene il link a my.telegram.org."""
        from PyQt6.QtWidgets import QLabel
        labels = dialog.findChildren(QLabel)
        info_texts = [l.text() for l in labels if "my.telegram.org" in l.text()]
        assert len(info_texts) >= 1


# ─── Caricamento Config ────────────────────────────────────────────────

class TestLoadConfig:
    """Test del caricamento configurazione nei campi."""

    def test_api_id_loaded(self, dialog, temp_config):
        assert dialog.api_id_edit.text() == temp_config["api_id"]

    def test_api_hash_loaded(self, dialog, temp_config):
        assert dialog.api_hash_edit.text() == temp_config["api_hash"]

    def test_phone_loaded(self, dialog, temp_config):
        assert dialog.phone_edit.text() == temp_config["phone"]

    def test_empty_config(self, qtbot):
        """Config senza campi popola con stringhe vuote."""
        dlg = AuthDialog({})
        qtbot.addWidget(dlg)
        assert dlg.api_id_edit.text() == ""
        assert dlg.api_hash_edit.text() == ""
        assert dlg.phone_edit.text() == ""


# ─── Validazione e Salvataggio ─────────────────────────────────────────

class TestValidation:
    """Test della validazione campi prima del salvataggio."""

    def test_valid_credentials_accept(self, dialog, qtbot):
        """Cliccare Salva con campi validi → accept() chiamato."""
        accepted = []
        dialog.accept = lambda: accepted.append(True)
        qtbot.mouseClick(dialog.action_btn, Qt.MouseButton.LeftButton)
        assert len(accepted) == 1

    def test_empty_fields_show_warning(self, dialog, monkeypatch):
        """Campi vuoti → QMessageBox.warning."""
        warnings = []
        monkeypatch.setattr(QMessageBox, "warning", lambda *a, **kw: warnings.append(True))
        dialog.api_id_edit.setText("")
        dialog.api_hash_edit.setText("")
        dialog.phone_edit.setText("")
        dialog._on_action()
        assert len(warnings) == 1

    def test_non_numeric_api_id_shows_warning(self, dialog, monkeypatch):
        """API ID non numerico → warning, accept NON chiamato."""
        warnings = []
        accepted = []
        monkeypatch.setattr(QMessageBox, "warning", lambda *a, **kw: warnings.append(True))
        dialog.accept = lambda: accepted.append(True)
        dialog.api_id_edit.setText("abc_not_a_number")
        dialog._on_action()
        assert len(warnings) == 1
        assert len(accepted) == 0

    def test_partial_fields_show_warning(self, dialog, monkeypatch):
        """Solo alcuni campi compilati → warning."""
        warnings = []
        monkeypatch.setattr(QMessageBox, "warning", lambda *a, **kw: warnings.append(True))
        dialog.api_id_edit.setText("12345")
        dialog.api_hash_edit.setText("")
        dialog.phone_edit.setText("+391234567890")
        dialog._on_action()
        assert len(warnings) == 1


# ─── Pulsanti ──────────────────────────────────────────────────────────

class TestButtons:
    """Test dei pulsanti Salva e Annulla."""

    def test_cancel_rejects(self, dialog, qtbot):
        rejected = []
        dialog.reject = lambda: rejected.append(True)
        qtbot.mouseClick(dialog.cancel_btn, Qt.MouseButton.LeftButton)
        assert len(rejected) == 1
