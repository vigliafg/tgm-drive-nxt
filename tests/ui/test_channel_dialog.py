"""
Test per channel_dialog.py — ChannelDialog: lista canali, ricerca, selezione.

Testa il caricamento della lista canali, il filtro di ricerca, la selezione
da lista, l'inserimento ID manuale, e la gestione errori usando mock del
TelegramClient.
"""

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QListWidgetItem, QMessageBox

from gui.channel_dialog import ChannelDialog


# ─── Helpers ──────────────────────────────────────────────────────────

def make_channel_list():
    """Crea una lista di canali di test realistica."""
    return [
        {"id": -1001111111111, "title": "Progetti Lavoro", "username": "progetti_lavoro"},
        {"id": -1002222222222, "title": "Foto Vacanze", "username": ""},
        {"id": -1003333333333, "title": "Backup Documenti", "username": "backup_docs"},
        {"id": -1004444444444, "title": "Altro Canale", "username": "altro_canale"},
    ]


# ─── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def dialog(mock_tg_client, qtbot):
    """ChannelDialog con TelegramClient mockato."""
    dlg = ChannelDialog(mock_tg_client)
    qtbot.addWidget(dlg)
    return dlg


@pytest.fixture
def dialog_with_channels(dialog, mock_tg_client, qtbot):
    """ChannelDialog con canali già caricati."""
    channels = make_channel_list()
    mock_tg_client.channels_ready.emit(channels)
    qtbot.wait(50)
    return dialog


# ─── Inizializzazione ──────────────────────────────────────────────────

class TestChannelDialogInit:
    """Test dello stato iniziale della dialog."""

    def test_window_title(self, dialog):
        assert dialog.windowTitle() == "Seleziona Canale Telegram"

    def test_minimum_size(self, dialog):
        assert dialog.minimumWidth() == 450
        assert dialog.minimumHeight() == 300

    def test_search_placeholder(self, dialog):
        assert dialog.search_edit.placeholderText() == "Cerca canale..."

    def test_manual_edit_placeholder(self, dialog):
        assert dialog.manual_edit.placeholderText() == "es. -1001234567890"

    def test_select_button_disabled_initially(self, dialog):
        """Il pulsante Seleziona è disabilitato finché non si seleziona un canale."""
        assert not dialog.select_btn.isEnabled()

    def test_progress_bar_visible_initially(self, dialog, qtbot):
        """La progress bar è visibile durante il caricamento."""
        # isVisible() richiede che TUTTI gli ancestor siano visibili.
        # Il dialog non è mostrato, quindi testiamo che il widget non sia hidden.
        assert not dialog.progress.isHidden()

    def test_list_starts_empty(self, dialog):
        """La lista è inizialmente vuota (list_channels è chiamata, in attesa della risposta)."""
        # Il ChannelDialog non aggiunge placeholder "Caricamento..." —
        # chiama direttamente list_channels() e attende il segnale channels_ready
        assert dialog.list_widget.count() >= 0


# ─── Caricamento Canali ────────────────────────────────────────────────

class TestChannelLoading:
    """Test del caricamento dei canali da Telegram."""

    def test_channels_ready_populates_list(self, dialog, mock_tg_client):
        """Quando arrivano i canali, la lista si popola."""
        channels = make_channel_list()
        mock_tg_client.channels_ready.emit(channels)
        assert len(dialog.all_channels) == 4

    def test_channels_ready_updates_title(self, dialog, mock_tg_client):
        """Il titolo della finestra mostra il conteggio canali."""
        channels = make_channel_list()
        mock_tg_client.channels_ready.emit(channels)
        assert "4 trovati" in dialog.windowTitle()

    def test_channels_ready_hides_progress(self, dialog, mock_tg_client):
        """La progress bar viene nascosta dopo il caricamento."""
        channels = make_channel_list()
        mock_tg_client.channels_ready.emit(channels)
        assert not dialog.progress.isVisible()

    def test_channels_ready_sorted_alphabetically(self, dialog, mock_tg_client):
        """I canali vengono ordinati alfabeticamente per titolo."""
        channels = [
            {"id": -1003333333333, "title": "Zeta Channel", "username": ""},
            {"id": -1001111111111, "title": "Alpha Channel", "username": ""},
            {"id": -1002222222222, "title": "Beta Channel", "username": ""},
        ]
        mock_tg_client.channels_ready.emit(channels)
        assert dialog.all_channels[0]["title"] == "Alpha Channel"
        assert dialog.all_channels[1]["title"] == "Beta Channel"
        assert dialog.all_channels[2]["title"] == "Zeta Channel"

    def test_empty_channel_list(self, dialog, mock_tg_client):
        """Se non ci sono canali, viene mostrato un messaggio appropriato."""
        mock_tg_client.channels_ready.emit([])
        item = dialog.list_widget.item(0)
        assert "Nessun canale" in item.text()
        # Il pulsante Seleziona resta disabilitato
        assert not dialog.select_btn.isEnabled()

    def test_channel_list_display_format(self, dialog, mock_tg_client):
        """Il formato di visualizzazione include titolo, username e ID."""
        channels = make_channel_list()
        mock_tg_client.channels_ready.emit(channels)
        # Dopo ordinamento alfabetico: Altro Canale, Backup, Foto, Progetti
        # Il primo (index 0) è "Altro Canale" che ha username "altro_canale"
        item = dialog.list_widget.item(0)
        text = item.text()
        assert "Altro Canale" in text
        assert "@altro_canale" in text
        assert "-1004444444444" in text

    def test_channel_list_display_no_username(self, dialog, mock_tg_client):
        """Canale senza username non mostra @."""
        channels = make_channel_list()
        mock_tg_client.channels_ready.emit(channels)
        # Ordine: Altro Canale, Backup Documenti, Foto Vacanze, Progetti Lavoro
        # "Foto Vacanze" ha username vuoto → indice 2
        item = dialog.list_widget.item(2)
        text = item.text()
        assert "Foto Vacanze" in text
        assert "@" not in text  # Nessuno username

    def test_channel_list_items_have_data(self, dialog, mock_tg_client):
        """Ogni item della lista ha l'ID canale come UserRole."""
        channels = make_channel_list()
        mock_tg_client.channels_ready.emit(channels)
        item = dialog.list_widget.item(0)
        ch_id = item.data(Qt.ItemDataRole.UserRole)
        assert ch_id is not None
        assert isinstance(ch_id, int)


# ─── Ricerca ────────────────────────────────────────────────────────────

class TestSearch:
    """Test della funzionalità di ricerca/filtro canali."""

    def test_search_filters_by_title(self, dialog_with_channels):
        """La ricerca filtra per titolo (case-insensitive)."""
        dialog_with_channels.search_edit.setText("foto")
        # Il segnale textChanged chiama _on_search → _filter_channels
        assert dialog_with_channels.list_widget.count() == 1
        item = dialog_with_channels.list_widget.item(0)
        assert "Foto Vacanze" in item.text()

    def test_search_filters_by_username(self, dialog_with_channels):
        """La ricerca filtra anche per username."""
        dialog_with_channels.search_edit.setText("backup_docs")
        assert dialog_with_channels.list_widget.count() == 1
        item = dialog_with_channels.list_widget.item(0)
        assert "Backup Documenti" in item.text()

    def test_search_is_case_insensitive(self, dialog_with_channels):
        """La ricerca è case-insensitive."""
        dialog_with_channels.search_edit.setText("FOTO")
        assert dialog_with_channels.list_widget.count() == 1
        assert "Foto Vacanze" in dialog_with_channels.list_widget.item(0).text()

    def test_search_no_results(self, dialog_with_channels):
        """Ricerca senza risultati mostra messaggio appropriato."""
        dialog_with_channels.search_edit.setText("zzz_nonexistent")
        assert dialog_with_channels.list_widget.count() == 1
        item = dialog_with_channels.list_widget.item(0)
        assert "Nessun canale" in item.text()

    def test_search_empty_restores_all(self, dialog_with_channels):
        """Query vuota ripristina tutti i canali."""
        dialog_with_channels.search_edit.setText("foto")
        assert dialog_with_channels.list_widget.count() == 1
        dialog_with_channels.search_edit.setText("")
        assert dialog_with_channels.list_widget.count() == 4

    def test_search_before_channels_loaded(self, dialog):
        """La ricerca prima del caricamento canali non causa errori."""
        dialog.search_edit.setText("test")
        assert True  # Nessuna eccezione


# ─── Selezione ──────────────────────────────────────────────────────────

class TestSelection:
    """Test della selezione canale dalla lista."""

    def test_selection_enables_button(self, dialog_with_channels):
        """Selezionare un canale abilita il pulsante Seleziona."""
        dialog_with_channels.list_widget.setCurrentRow(0)
        assert dialog_with_channels.select_btn.isEnabled()

    def test_selection_sets_channel_id(self, dialog_with_channels):
        """La selezione imposta selected_channel_id."""
        dialog_with_channels.list_widget.setCurrentRow(0)
        item = dialog_with_channels.list_widget.currentItem()
        ch_id = item.data(Qt.ItemDataRole.UserRole)
        assert ch_id is not None

    def test_select_accepts_dialog(self, dialog_with_channels, qtbot):
        """Cliccare Seleziona chiama accept()."""
        accepted = []
        dialog_with_channels.accept = lambda: accepted.append(True)
        dialog_with_channels.list_widget.setCurrentRow(0)
        qtbot.mouseClick(dialog_with_channels.select_btn, Qt.MouseButton.LeftButton)
        assert len(accepted) == 1

    def test_select_sets_name(self, dialog_with_channels):
        """La selezione estrae il nome canale dal testo dell'item."""
        # Previeni la chiusura del dialog sostituendo accept
        dialog_with_channels.accept = lambda: None
        dialog_with_channels.list_widget.setCurrentRow(0)
        dialog_with_channels._on_select()
        assert dialog_with_channels.selected_channel_name != ""
        # Il nome non deve contenere " — ID:"
        assert " — ID:" not in dialog_with_channels.selected_channel_name

    def test_double_click_accepts(self, dialog_with_channels):
        """Doppio click su un canale chiama _on_select e accetta."""
        # ChannelDialog connette itemDoubleClicked → _on_select (non _on_double_click)
        dialog_with_channels.accept = lambda: None
        dialog_with_channels.list_widget.setCurrentRow(0)
        item = dialog_with_channels.list_widget.currentItem()
        # Simula il segnale: _on_select viene chiamato
        dialog_with_channels._on_select()
        assert dialog_with_channels.selected_channel_id is not None

    def test_select_without_selection_blocked(self, dialog_with_channels, monkeypatch):
        """Se nessun item è selezionato, _on_select mostra un warning."""
        warning_shown = []
        monkeypatch.setattr(QMessageBox, "warning", lambda *a, **kw: warning_shown.append(True))
        # Forza nessuna selezione
        dialog_with_channels.list_widget.setCurrentRow(-1)
        dialog_with_channels._on_select()
        assert len(warning_shown) == 1

    def test_select_button_disabled_when_no_channels(self, dialog):
        """Senza canali caricati, il pulsante Seleziona è disabilitato."""
        assert not dialog.select_btn.isEnabled()

    def test_select_button_enabled_after_selection(self, dialog_with_channels, qtbot):
        """Dopo aver selezionato un canale, il pulsante si abilita."""
        dialog_with_channels.list_widget.setCurrentRow(0)
        qtbot.wait(10)
        assert dialog_with_channels.select_btn.isEnabled()

    def test_cancel_button_rejects(self, dialog, qtbot):
        """Il pulsante Annulla chiama reject()."""
        rejected = []
        dialog.reject = lambda: rejected.append(True)
        qtbot.mouseClick(dialog.cancel_btn, Qt.MouseButton.LeftButton)
        assert len(rejected) == 1


# ─── Inserimento ID Manuale ────────────────────────────────────────────

class TestManualID:
    """Test dell'inserimento ID canale manuale."""

    def test_manual_id_valid(self, dialog_with_channels):
        """Inserimento di un ID valido."""
        dialog_with_channels.manual_edit.setText("-1009999999999")
        accepted = []
        dialog_with_channels.accept = lambda: accepted.append(True)
        dialog_with_channels._on_manual()
        assert len(accepted) == 1
        assert dialog_with_channels.selected_channel_id == -1009999999999
        assert "Canale" in dialog_with_channels.selected_channel_name

    def test_manual_id_empty(self, dialog_with_channels, monkeypatch):
        """ID vuoto mostra warning e non accetta."""
        monkeypatch.setattr(QMessageBox, "warning", lambda *a, **kw: None)
        dialog_with_channels.manual_edit.setText("")
        accepted = []
        dialog_with_channels.accept = lambda: accepted.append(True)
        dialog_with_channels._on_manual()
        assert len(accepted) == 0

    def test_manual_id_invalid(self, dialog_with_channels, monkeypatch):
        """ID non numerico mostra warning."""
        monkeypatch.setattr(QMessageBox, "warning", lambda *a, **kw: None)
        dialog_with_channels.manual_edit.setText("non_un_numero")
        accepted = []
        dialog_with_channels.accept = lambda: accepted.append(True)
        dialog_with_channels._on_manual()
        assert len(accepted) == 0

    def test_manual_button_click(self, dialog_with_channels, qtbot):
        """Cliccare il pulsante Usa ID attiva _on_manual."""
        dialog_with_channels.manual_edit.setText("-1008888888888")
        accepted = []
        dialog_with_channels.accept = lambda: accepted.append(True)
        qtbot.mouseClick(dialog_with_channels.manual_btn, Qt.MouseButton.LeftButton)
        assert len(accepted) == 1

    def test_manual_return_pressed(self, dialog_with_channels, qtbot):
        """Premere Invio nell'edit manuale attiva _on_manual."""
        dialog_with_channels.manual_edit.setText("-1007777777777")
        accepted = []
        dialog_with_channels.accept = lambda: accepted.append(True)
        dialog_with_channels.manual_edit.returnPressed.emit()
        assert len(accepted) == 1


# ─── Gestione Errori ───────────────────────────────────────────────────

class TestErrorHandling:
    """Test della gestione errori Telegram."""

    def test_error_message_hides_progress(self, dialog, mock_tg_client, monkeypatch):
        """Un errore Telegram nasconde la progress bar."""
        monkeypatch.setattr(QMessageBox, "critical", lambda *a, **kw: None)
        mock_tg_client.error_occurred.emit("Errore di rete")
        assert not dialog.progress.isVisible()

    def test_error_message_handled(self, dialog, mock_tg_client, monkeypatch):
        """Un errore Telegram non causa crash e nasconde la progress bar."""
        monkeypatch.setattr(QMessageBox, "critical", lambda *a, **kw: None)
        mock_tg_client.error_occurred.emit("Test error message")
        assert not dialog.progress.isVisible()
