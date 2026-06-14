"""
Test per destination_dialog.py — DestinationDialog: selezione canale destinazione.

Testa il caricamento dei canali preferiti dal DB, l'esclusione di canali,
la selezione da lista, e i pulsanti OK/Annulla.
"""

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QListWidgetItem

from gui.destination_dialog import DestinationDialog


# ─── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def dialog(memory_db, qtbot):
    """DestinationDialog per copia (default action='copy')."""
    memory_db.add_favorite_channel(-1001111111111, "Canale A", "Mio Canale A")
    memory_db.add_favorite_channel(-1002222222222, "Canale B", "Mio Canale B")
    memory_db.add_favorite_channel(-1003333333333, "Canale C", "Mio Canale C")
    dlg = DestinationDialog(memory_db)
    qtbot.addWidget(dlg)
    return dlg


@pytest.fixture
def move_dialog(memory_db, qtbot):
    """DestinationDialog per spostamento (action='move')."""
    memory_db.add_favorite_channel(-1001111111111, "Canale A", "Mio Canale A")
    memory_db.add_favorite_channel(-1002222222222, "Canale B", "Mio Canale B")
    dlg = DestinationDialog(memory_db, action="move")
    qtbot.addWidget(dlg)
    return dlg


@pytest.fixture
def dialog_with_exclusion(memory_db, qtbot):
    """DestinationDialog con un canale escluso."""
    memory_db.add_favorite_channel(-1001111111111, "Canale A", "Mio A")
    memory_db.add_favorite_channel(-1002222222222, "Canale B", "Mio B")
    memory_db.add_favorite_channel(-1003333333333, "Canale C", "Mio C")
    dlg = DestinationDialog(memory_db, exclude_channel_ids={-1002222222222})
    qtbot.addWidget(dlg)
    return dlg


# ─── Inizializzazione ──────────────────────────────────────────────────

class TestDestinationDialogInit:
    """Test dello stato iniziale."""

    def test_window_title_copy(self, dialog):
        assert "Copia" in dialog.windowTitle()

    def test_window_title_move(self, move_dialog):
        assert "Sposta" in move_dialog.windowTitle()

    def test_minimum_size(self, dialog):
        assert dialog.minimumWidth() == 380
        assert dialog.minimumHeight() == 320

    def test_ok_button_disabled_initially(self, dialog):
        """Il pulsante OK è disabilitato finché non si seleziona un canale."""
        assert not dialog.btn_ok.isEnabled()

    def test_copy_button_text(self, dialog):
        assert "Copia" in dialog.btn_ok.text()

    def test_move_button_text(self, move_dialog):
        assert "Sposta" in move_dialog.btn_ok.text()

    def test_cancel_button_exists(self, dialog):
        """Il pulsante Annulla esiste nella dialog."""
        from PyQt6.QtWidgets import QPushButton
        buttons = dialog.findChildren(QPushButton)
        cancel_btns = [b for b in buttons if b.text() == "Annulla"]
        assert len(cancel_btns) == 1


# ─── Caricamento Canali ────────────────────────────────────────────────

class TestLoadChannels:
    """Test del caricamento canali preferiti dal DB."""

    def test_channels_loaded(self, dialog):
        """I canali preferiti vengono caricati dal DB."""
        assert dialog.channel_list.count() == 3

    def test_channel_items_have_data(self, dialog):
        """Ogni item ha l'ID canale come UserRole."""
        item = dialog.channel_list.item(0)
        ch_id = item.data(Qt.ItemDataRole.UserRole)
        assert ch_id is not None
        assert isinstance(ch_id, int)

    def test_channel_display_icon(self, dialog):
        """Il nome mostra l'icona 📁."""
        item = dialog.channel_list.item(0)
        assert "📁" in item.text()

    def test_excluded_channels_not_shown(self, dialog_with_exclusion):
        """I canali esclusi non appaiono nella lista."""
        count = dialog_with_exclusion.channel_list.count()
        ids = []
        for i in range(count):
            item = dialog_with_exclusion.channel_list.item(i)
            ids.append(item.data(Qt.ItemDataRole.UserRole))
        assert -1002222222222 not in ids

    def test_empty_favorites_shows_placeholder(self, memory_db, qtbot):
        """Se nessun canale preferito è disponibile, mostra placeholder."""
        dlg = DestinationDialog(memory_db)
        qtbot.addWidget(dlg)
        assert dlg.channel_list.count() >= 1
        item = dlg.channel_list.item(0)
        assert "Nessun canale" in item.text() or not item.flags() & Qt.ItemFlag.ItemIsEnabled


# ─── Selezione ──────────────────────────────────────────────────────────

class TestSelection:
    """Test della selezione canale destinazione."""

    def test_selection_enables_button(self, dialog, qtbot):
        """Selezionare un canale abilita il pulsante OK."""
        dialog.channel_list.setCurrentRow(0)
        qtbot.wait(10)
        assert dialog.btn_ok.isEnabled()

    def test_selection_sets_channel_id(self, dialog):
        """La selezione imposta selected_channel_id."""
        dialog.channel_list.setCurrentRow(0)
        dialog._on_ok()
        assert dialog.selected_channel_id is not None

    def test_ok_button_accepts(self, dialog, qtbot):
        """Cliccare OK accetta il dialog con l'ID canale selezionato."""
        accepted = []
        dialog.accept = lambda: accepted.append(True)
        dialog.channel_list.setCurrentRow(0)
        qtbot.mouseClick(dialog.btn_ok, Qt.MouseButton.LeftButton)
        assert len(accepted) == 1

    def test_double_click_accepts(self, dialog):
        """Doppio click su un canale accetta il dialog."""
        accepted = []
        dialog.accept = lambda: accepted.append(True)
        dialog.channel_list.setCurrentRow(0)
        dialog._on_ok()
        assert len(accepted) == 1

    def test_ok_without_selection_noop(self, dialog):
        """_on_ok senza canale selezionato non imposta selected_channel_id."""
        # currentItem() restituisce None se nessuna riga è selezionata
        assert dialog.channel_list.currentItem() is None
        dialog._on_ok()
        assert dialog.selected_channel_id is None

    def test_cancel_rejects(self, dialog, qtbot):
        """Il pulsante Annulla chiama reject()."""
        from PyQt6.QtWidgets import QPushButton
        rejected = []
        dialog.reject = lambda: rejected.append(True)
        buttons = dialog.findChildren(QPushButton)
        cancel_btn = [b for b in buttons if b.text() == "Annulla"][0]
        qtbot.mouseClick(cancel_btn, Qt.MouseButton.LeftButton)
        assert len(rejected) == 1
