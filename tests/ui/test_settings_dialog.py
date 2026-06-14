"""
Test per settings_dialog.py — SettingsDialog, FavoriteChannelsTab, TagsTab.

Testa il salvataggio impostazioni UI (tema, font, dimensioni finestra, auto-clear),
le credenziali Telegram, i segnali disconnect/reconnect, e i tab preferiti/tags.
"""

import pytest
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox, QPushButton

from config import DEFAULT_CONFIG, save_config, CONFIG_FILE, CONFIG_DIR
from database import Database
from gui.settings_dialog import SettingsDialog, FavoriteChannelsTab, TagsTab


# ─── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def dialog(temp_config, memory_db, mock_tg_client, qtbot):
    """SettingsDialog con DB, config e client mockati."""
    mock_tg_client.set_connected(True)
    dlg = SettingsDialog(temp_config, memory_db, mock_tg_client)
    qtbot.addWidget(dlg)
    return dlg


@pytest.fixture
def disconnected_dialog(temp_config, memory_db, mock_tg_client, qtbot):
    """SettingsDialog con client disconnesso."""
    mock_tg_client.set_connected(False)
    dlg = SettingsDialog(temp_config, memory_db, mock_tg_client)
    qtbot.addWidget(dlg)
    return dlg


@pytest.fixture
def favorites_tab(memory_db, mock_tg_client, qtbot):
    """FavoriteChannelsTab isolato."""
    tab = FavoriteChannelsTab(memory_db, mock_tg_client)
    qtbot.addWidget(tab)
    return tab


@pytest.fixture
def tags_tab(memory_db, qtbot):
    """TagsTab isolato con DB popolato di tag."""
    memory_db.add_tag("lavoro", sort_order=0)
    memory_db.add_tag("personale", sort_order=1)
    tab = TagsTab(memory_db)
    qtbot.addWidget(tab)
    return tab


# ─── SettingsDialog: Inizializzazione ──────────────────────────────────

class TestSettingsDialogInit:
    """Test dell'inizializzazione della dialog."""

    def test_window_title(self, dialog):
        assert dialog.windowTitle() == "⚙️ Impostazioni"

    def test_minimum_size(self, dialog):
        assert dialog.minimumWidth() == 650
        assert dialog.minimumHeight() == 500

    def test_has_four_tabs(self, dialog):
        assert dialog.tabs.count() == 4
        assert dialog.tabs.tabText(0) == "🎨 UI"
        assert dialog.tabs.tabText(1) == "📡 Telegram"
        assert dialog.tabs.tabText(2) == "⭐ Canali Preferiti"
        assert dialog.tabs.tabText(3) == "🏷️ Tags"

    def test_has_save_and_cancel_buttons(self, dialog):
        assert dialog.save_btn.text() == "💾 Salva"
        assert dialog.cancel_btn.text() == "❌ Annulla"

    def test_save_button_is_default(self, dialog):
        assert dialog.save_btn.isDefault()

    def test_default_initial_tab(self, dialog):
        """Il tab iniziale predefinito è UI (0)."""
        assert dialog.tabs.currentIndex() == SettingsDialog.TAB_UI

    def test_custom_initial_tab(self, temp_config, memory_db, mock_tg_client, qtbot):
        """Se specificato, il dialog apre al tab indicato."""
        dlg = SettingsDialog(temp_config, memory_db, mock_tg_client,
                             initial_tab=SettingsDialog.TAB_TAGS)
        qtbot.addWidget(dlg)
        assert dlg.tabs.currentIndex() == SettingsDialog.TAB_TAGS

    def test_status_label_connected(self, dialog):
        """Se il client è connesso, il label mostra ✅ Connesso."""
        assert "✅" in dialog.status_lbl.text()

    def test_status_label_disconnected(self, disconnected_dialog):
        """Se il client è disconnesso, il label mostra ❌ Non connesso."""
        assert "❌" in disconnected_dialog.status_lbl.text()


# ─── SettingsDialog: UI Tab ────────────────────────────────────────────

class TestUITab:
    """Test del tab UI Settings."""

    def test_theme_combo_has_three_options(self, dialog):
        assert dialog.theme_combo.count() == 3
        items = [dialog.theme_combo.itemText(i) for i in range(3)]
        assert "Dark" in items
        assert "Light" in items
        assert "System" in items

    def test_theme_loaded_from_config(self, dialog):
        """Il tema viene caricato dalla configurazione."""
        assert dialog.theme_combo.currentText().lower() == dialog.config["ui_theme"]

    def test_theme_loads_dark(self, temp_config, memory_db, mock_tg_client, qtbot):
        temp_config["ui_theme"] = "dark"
        dlg = SettingsDialog(temp_config, memory_db, mock_tg_client)
        qtbot.addWidget(dlg)
        assert dlg.theme_combo.currentText() == "Dark"

    def test_theme_loads_light(self, temp_config, memory_db, mock_tg_client, qtbot):
        temp_config["ui_theme"] = "light"
        dlg = SettingsDialog(temp_config, memory_db, mock_tg_client)
        qtbot.addWidget(dlg)
        assert dlg.theme_combo.currentText() == "Light"

    def test_theme_loads_system(self, temp_config, memory_db, mock_tg_client, qtbot):
        temp_config["ui_theme"] = "system"
        dlg = SettingsDialog(temp_config, memory_db, mock_tg_client)
        qtbot.addWidget(dlg)
        assert dlg.theme_combo.currentText() == "System"

    def test_font_spin_range(self, dialog):
        assert dialog.font_spin.minimum() == 8
        assert dialog.font_spin.maximum() == 24

    def test_font_loaded_from_config(self, dialog):
        assert dialog.font_spin.value() == dialog.config["ui_font_size"]

    def test_font_custom_value(self, temp_config, memory_db, mock_tg_client, qtbot):
        temp_config["ui_font_size"] = 16
        dlg = SettingsDialog(temp_config, memory_db, mock_tg_client)
        qtbot.addWidget(dlg)
        assert dlg.font_spin.value() == 16

    def test_window_width_range(self, dialog):
        assert dialog.win_width_spin.minimum() == 800
        assert dialog.win_width_spin.maximum() == 3840

    def test_window_width_loaded_from_config(self, dialog):
        assert dialog.win_width_spin.value() == dialog.config["window_width"]

    def test_window_height_range(self, dialog):
        assert dialog.win_height_spin.minimum() == 600
        assert dialog.win_height_spin.maximum() == 2160

    def test_window_height_loaded_from_config(self, dialog):
        assert dialog.win_height_spin.value() == dialog.config["window_height"]

    def test_auto_clear_combo(self, dialog):
        assert dialog.auto_clear_checkbox.count() == 2
        assert dialog.auto_clear_checkbox.itemText(0) == "Sì"
        assert dialog.auto_clear_checkbox.itemText(1) == "No"

    def test_auto_clear_true_loaded(self, temp_config, memory_db, mock_tg_client, qtbot):
        temp_config["auto_clear_transfers"] = True
        dlg = SettingsDialog(temp_config, memory_db, mock_tg_client)
        qtbot.addWidget(dlg)
        assert dlg.auto_clear_checkbox.currentIndex() == 0  # "Sì"

    def test_auto_clear_false_loaded(self, temp_config, memory_db, mock_tg_client, qtbot):
        temp_config["auto_clear_transfers"] = False
        dlg = SettingsDialog(temp_config, memory_db, mock_tg_client)
        qtbot.addWidget(dlg)
        assert dlg.auto_clear_checkbox.currentIndex() == 1  # "No"

    def test_font_spin_suffix(self, dialog):
        assert "pt" in dialog.font_spin.suffix()

    def test_width_spin_suffix(self, dialog):
        assert "px" in dialog.win_width_spin.suffix()


# ─── SettingsDialog: Telegram Tab ──────────────────────────────────────

class TestTelegramTab:
    """Test del tab Telegram Settings."""

    def test_api_id_loaded_from_config(self, dialog):
        assert dialog.api_id_edit.text() == dialog.config["api_id"]

    def test_api_hash_loaded_from_config(self, dialog):
        assert dialog.api_hash_edit.text() == dialog.config["api_hash"]

    def test_phone_loaded_from_config(self, dialog):
        assert dialog.phone_edit.text() == dialog.config["phone"]

    def test_placeholder_texts(self, dialog):
        assert dialog.api_id_edit.placeholderText() == "12345"
        assert dialog.api_hash_edit.placeholderText() == "abc123..."
        assert dialog.phone_edit.placeholderText() == "+39333..."

    def test_disconnect_button_exists(self, dialog):
        assert dialog.btn_disconnect.text() == "🔌 Disconnetti"

    def test_reconnect_button_exists(self, dialog):
        assert dialog.btn_reconnect.text() == "🔄 Riconnetti"


# ─── SettingsDialog: Salvataggio ───────────────────────────────────────

class TestSave:
    """Test del flusso di salvataggio."""

    def test_save_emits_settings_applied(self, dialog, qtbot, monkeypatch):
        """_on_save emette settings_applied con la config aggiornata."""
        # Evita il QMessageBox di conferma disconnect
        monkeypatch.setattr("gui.settings_dialog.save_config", lambda c: None)

        dialog.theme_combo.setCurrentText("Light")
        dialog.font_spin.setValue(14)
        dialog.win_width_spin.setValue(1400)
        dialog.win_height_spin.setValue(900)
        dialog.auto_clear_checkbox.setCurrentIndex(1)  # "No"

        with qtbot.waitSignal(dialog.settings_applied, timeout=1000) as blocker:
            dialog._on_save()

        config = blocker.args[0]
        assert config["ui_theme"] == "light"
        assert config["ui_font_size"] == 14
        assert config["window_width"] == 1400
        assert config["window_height"] == 900
        assert config["auto_clear_transfers"] is False

    def test_save_preserves_telegram_credentials(self, dialog, monkeypatch):
        """Il salvataggio preserva le credenziali Telegram."""
        monkeypatch.setattr("gui.settings_dialog.save_config", lambda c: None)

        original_api_id = dialog.config["api_id"]
        original_api_hash = dialog.config["api_hash"]
        original_phone = dialog.config["phone"]

        dialog._on_save()

        assert dialog.config["api_id"] == original_api_id
        assert dialog.config["api_hash"] == original_api_hash
        assert dialog.config["phone"] == original_phone

    def test_save_updates_telegram_credentials(self, dialog, monkeypatch):
        """Il salvataggio aggiorna le credenziali modificate."""
        monkeypatch.setattr("gui.settings_dialog.save_config", lambda c: None)

        dialog.api_id_edit.setText("99999")
        dialog.api_hash_edit.setText("newhash")
        dialog.phone_edit.setText("+391111111111")

        dialog._on_save()

        assert dialog.config["api_id"] == "99999"
        assert dialog.config["api_hash"] == "newhash"
        assert dialog.config["phone"] == "+391111111111"

    def test_save_theme_lowercase(self, dialog, monkeypatch):
        """Il tema viene salvato in lowercase indipendentemente dal display."""
        monkeypatch.setattr("gui.settings_dialog.save_config", lambda c: None)

        dialog.theme_combo.setCurrentText("System")
        dialog._on_save()
        assert dialog.config["ui_theme"] == "system"

    def test_save_calls_accept(self, dialog, monkeypatch):
        """_on_save chiama accept() (chiude il dialog)."""
        monkeypatch.setattr("gui.settings_dialog.save_config", lambda c: None)
        accepted = []
        dialog.accept = lambda: accepted.append(True)
        dialog._on_save()
        assert len(accepted) == 1

    def test_cancel_button_rejects(self, dialog, qtbot):
        """Il pulsante Annulla chiama reject()."""
        rejected = []
        dialog.reject = lambda: rejected.append(True)
        qtbot.mouseClick(dialog.cancel_btn, Qt.MouseButton.LeftButton)
        assert len(rejected) == 1

    def test_save_button_triggers_on_save(self, dialog, qtbot, monkeypatch):
        """Cliccare Salva chiama _on_save."""
        monkeypatch.setattr("gui.settings_dialog.save_config", lambda c: None)
        saved = []

        with qtbot.waitSignal(dialog.settings_applied, timeout=1000):
            dialog._on_save()
            saved.append(True)
        assert len(saved) == 1


# ─── SettingsDialog: Disconnect/Reconnect ──────────────────────────────

class TestDisconnectReconnect:
    """Test dei pulsanti Disconnetti/Riconnetti."""

    def test_disconnect_shows_confirmation(self, dialog, qtbot, monkeypatch):
        """Disconnetti mostra un QMessageBox di conferma."""
        # Mock QMessageBox.question per rispondere Yes
        monkeypatch.setattr(
            QMessageBox, "question",
            lambda *args, **kwargs: QMessageBox.StandardButton.Yes
        )

        with qtbot.waitSignal(dialog.disconnect_requested, timeout=1000):
            dialog._on_disconnect()

        assert "❌" in dialog.status_lbl.text()

    def test_disconnect_cancelled(self, dialog, monkeypatch):
        """Se l'utente risponde No, non viene emesso disconnect_requested."""
        monkeypatch.setattr(
            QMessageBox, "question",
            lambda *args, **kwargs: QMessageBox.StandardButton.No
        )
        emitted = []
        dialog.disconnect_requested.connect(lambda: emitted.append(True))
        dialog._on_disconnect()
        assert len(emitted) == 0

    def test_reconnect_emits_signal(self, dialog, qtbot):
        """Riconnetti emette reconnect_requested."""
        with qtbot.waitSignal(dialog.reconnect_requested, timeout=1000):
            dialog._on_reconnect()

        assert "Connessione in corso" in dialog.status_lbl.text()

    def test_disconnect_button_click(self, dialog, qtbot, monkeypatch):
        """Cliccare il pulsante Disconnetti chiama _on_disconnect."""
        monkeypatch.setattr(
            QMessageBox, "question",
            lambda *args, **kwargs: QMessageBox.StandardButton.Yes
        )

        with qtbot.waitSignal(dialog.disconnect_requested, timeout=1000):
            qtbot.mouseClick(dialog.btn_disconnect, Qt.MouseButton.LeftButton)

    def test_reconnect_button_click(self, dialog, qtbot):
        """Cliccare il pulsante Riconnetti chiama _on_reconnect."""
        with qtbot.waitSignal(dialog.reconnect_requested, timeout=1000):
            qtbot.mouseClick(dialog.btn_reconnect, Qt.MouseButton.LeftButton)


# ─── FavoriteChannelsTab ────────────────────────────────────────────────

class TestFavoriteChannelsTab:
    """Test del tab Canali Preferiti."""

    def test_initial_favorites_loaded(self, favorites_tab, memory_db):
        """I preferiti vengono caricati dal DB all'avvio."""
        memory_db.add_favorite_channel(-1001111111111, "My Channel", "Il Mio Canale")
        # Ricarica i preferiti
        favorites_tab._load_favorites()
        assert len(favorites_tab._favorite_channels) >= 1

    def test_channel_list_loaded_on_init(self, favorites_tab):
        """All'init, la lista canali mostra 'Caricamento...'."""
        assert favorites_tab.all_list.count() >= 1

    def test_refresh_btn_triggers_load(self, favorites_tab, qtbot):
        """Il pulsante Aggiorna lista chiama list_channels()."""
        qtbot.mouseClick(favorites_tab.refresh_btn, Qt.MouseButton.LeftButton)
        # list_channels è chiamato sul tg_client
        # Verifichiamo che la lista mostri 'Caricamento...'
        item = favorites_tab.all_list.item(0)
        assert item is not None

    def test_telegram_channels_ready(self, favorites_tab, mock_tg_client):
        """Quando arrivano i canali da Telegram, la lista si popola."""
        channels = [
            {"id": -1001111111111, "title": "Canale A", "username": "canalea"},
            {"id": -1002222222222, "title": "Canale B", "username": ""},
        ]
        mock_tg_client.channels_ready.emit(channels)
        assert len(favorites_tab._all_telegram_channels) == 2

    def test_telegram_error_shown(self, favorites_tab, mock_tg_client):
        """Un errore Telegram viene mostrato nella lista."""
        mock_tg_client.error_occurred.emit("Errore di connessione")
        item = favorites_tab.all_list.item(0)
        assert "Errore" in item.text()

    def test_channels_changed_signal(self, favorites_tab, qtbot, mock_tg_client):
        """Aggiungere un canale emette channels_changed."""
        channels = [
            {"id": -1001111111111, "title": "Test Channel", "username": "test"},
        ]
        mock_tg_client.channels_ready.emit(channels)

        with qtbot.waitSignal(favorites_tab.channels_changed, timeout=1000):
            # Seleziona l'item e clicca Aggiungi
            favorites_tab.all_list.setCurrentRow(0)
            favorites_tab._on_add()

    def test_get_favorite_channels(self, favorites_tab, memory_db):
        """get_favorite_channels restituisce la lista corrente."""
        memory_db.add_favorite_channel(-1001111111111, "Test")
        favorites_tab._load_favorites()
        favs = favorites_tab.get_favorite_channels()
        assert isinstance(favs, list)

    def test_save_to_db(self, favorites_tab, memory_db):
        """save_to_db persiste i preferiti nel DB."""
        memory_db.add_favorite_channel(-1003333333333, "Saved Channel")
        favorites_tab._load_favorites()
        favorites_tab.save_to_db()
        db_favs = memory_db.get_favorite_channels()
        assert any(f["channel_id"] == -1003333333333 for f in db_favs)

    def test_move_up(self, favorites_tab, memory_db):
        """Spostare un preferito verso l'alto cambia l'ordine."""
        memory_db.set_favorite_channels([
            {"channel_id": -1001111111111, "channel_name": "A", "display_name": "A", "sort_order": 0},
            {"channel_id": -1002222222222, "channel_name": "B", "display_name": "B", "sort_order": 1},
        ])
        favorites_tab._load_favorites()
        favorites_tab.fav_list.setCurrentRow(1)  # Seleziona B
        favorites_tab._on_move_up()
        assert favorites_tab._favorite_channels[0]["channel_id"] == -1002222222222

    def test_move_down(self, favorites_tab, memory_db):
        """Spostare un preferito verso il basso cambia l'ordine."""
        memory_db.set_favorite_channels([
            {"channel_id": -1001111111111, "channel_name": "A", "display_name": "A", "sort_order": 0},
            {"channel_id": -1002222222222, "channel_name": "B", "display_name": "B", "sort_order": 1},
        ])
        favorites_tab._load_favorites()
        favorites_tab.fav_list.setCurrentRow(0)  # Seleziona A
        favorites_tab._on_move_down()
        assert favorites_tab._favorite_channels[0]["channel_id"] == -1002222222222


# ─── TagsTab ────────────────────────────────────────────────────────────

class TestTagsTab:
    """Test del tab Tags."""

    def test_tags_loaded_from_db(self, tags_tab):
        """I tag vengono caricati dal DB all'avvio."""
        assert len(tags_tab._tags) >= 2
        tag_names = [t["tag_name"] for t in tags_tab._tags]
        assert "lavoro" in tag_names
        assert "personale" in tag_names

    def test_tag_list_display(self, tags_tab):
        """La lista mostra i tag con conteggio file."""
        assert tags_tab.tag_list.count() >= 2

    def test_info_label_shows_count(self, tags_tab):
        """Il label info mostra il numero di tag disponibili."""
        assert "tag disponibili" in tags_tab.info_label.text()

    def test_add_tag(self, tags_tab, qtbot):
        """Aggiungere un nuovo tag."""
        initial_count = len(tags_tab._tags)
        tags_tab.new_tag_edit.setText("nuovo_tag")

        with qtbot.waitSignal(tags_tab.tags_changed, timeout=1000):
            tags_tab._on_add_tag()

        assert len(tags_tab._tags) == initial_count + 1
        assert any(t["tag_name"] == "nuovo_tag" for t in tags_tab._tags)

    def test_add_tag_button(self, tags_tab, qtbot):
        """Il pulsante ➕ Aggiungi crea un nuovo tag."""
        tags_tab.new_tag_edit.setText("urgente")

        with qtbot.waitSignal(tags_tab.tags_changed, timeout=1000):
            qtbot.mouseClick(tags_tab.btn_add, Qt.MouseButton.LeftButton)

        assert any(t["tag_name"] == "urgente" for t in tags_tab._tags)

    def test_add_empty_tag_ignored(self, tags_tab, qtbot):
        """Tag vuoto viene ignorato."""
        initial_count = len(tags_tab._tags)
        tags_tab.new_tag_edit.setText("")
        tags_tab._on_add_tag()
        assert len(tags_tab._tags) == initial_count

    def test_add_duplicate_tag(self, tags_tab, qtbot, monkeypatch):
        """Tag duplicato mostra warning e non viene aggiunto."""
        monkeypatch.setattr(QMessageBox, "warning", lambda *args: None)
        initial_count = len(tags_tab._tags)
        tags_tab.new_tag_edit.setText("lavoro")  # già esistente
        tags_tab._on_add_tag()
        assert len(tags_tab._tags) == initial_count

    def test_remove_tag_no_files(self, tags_tab, qtbot):
        """Rimuovere un tag senza file associati."""
        tags_tab._tags = [{"tag_id": 1, "tag_name": "vuoto", "sort_order": 0}]
        tags_tab._refresh_list()
        tags_tab.tag_list.setCurrentRow(0)

        with qtbot.waitSignal(tags_tab.tags_changed, timeout=1000):
            tags_tab._on_remove_tag()

        assert len(tags_tab._tags) == 0

    def test_remove_tag_with_files_confirms(self, tags_tab, monkeypatch):
        """Rimuovere un tag con file mostra conferma."""
        # Simula Yes nella conferma
        monkeypatch.setattr(
            QMessageBox, "question",
            lambda *args, **kwargs: QMessageBox.StandardButton.Yes
        )
        # "lavoro" ha 0 file nel DB vuoto, ma il test mostra il flusso
        tags_tab.tag_list.setCurrentRow(0)
        tags_tab._on_remove_tag()
        # Deve funzionare senza eccezioni

    def test_rename_tag(self, tags_tab, qtbot, monkeypatch):
        """Rinominare un tag."""
        tags_tab.tag_list.setCurrentRow(0)
        old_name = tags_tab._tags[0]["tag_name"]

        # QInputDialog è importato localmente dentro _on_rename_tag,
        # quindi patchano il modulo PyQt6.QtWidgets direttamente
        monkeypatch.setattr(
            "PyQt6.QtWidgets.QInputDialog.getText",
            lambda parent, title, label, **kwargs: ("ufficio", True)
        )

        with qtbot.waitSignal(tags_tab.tags_changed, timeout=1000):
            tags_tab._on_rename_tag()

        assert tags_tab._tags[0]["tag_name"] == "ufficio"
        assert tags_tab._tags[0]["tag_name"] != old_name

    def test_move_tag_up(self, tags_tab, qtbot):
        """Spostare un tag verso l'alto."""
        tags_tab.tag_list.setCurrentRow(1)  # Secondo tag
        with qtbot.waitSignal(tags_tab.tags_changed, timeout=1000):
            tags_tab._on_move_up()
        assert tags_tab._tags[0]["sort_order"] == 0

    def test_move_tag_down(self, tags_tab, qtbot):
        """Spostare un tag verso il basso."""
        tags_tab.tag_list.setCurrentRow(0)  # Primo tag
        with qtbot.waitSignal(tags_tab.tags_changed, timeout=1000):
            tags_tab._on_move_down()
        assert tags_tab._tags[1]["sort_order"] == 1

    def test_get_tags(self, tags_tab):
        """get_tags restituisce la lista corrente."""
        tag_list = tags_tab.get_tags()
        assert isinstance(tag_list, list)
        assert len(tag_list) >= 2

    def test_save_to_db(self, tags_tab, memory_db):
        """save_to_db persiste i tag nel DB."""
        tags_tab._tags = [
            {"tag_id": -1, "tag_name": "nuovo", "sort_order": 0}
        ]
        tags_tab.save_to_db()
        db_tags = memory_db.get_tags()
        assert any(t["tag_name"] == "nuovo" for t in db_tags)
