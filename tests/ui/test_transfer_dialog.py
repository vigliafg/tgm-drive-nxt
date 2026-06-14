"""
Test per transfer_dialog.py — TransferDialog, TransferItem e ciclo di vita.

Questi test usano pytest-qt (qtbot) per interagire con i widget.
"""

from pathlib import Path

import pytest
from PyQt6.QtCore import Qt, pyqtSignal, QObject

from gui.transfer_manager import TransferManager, TransferOp
from gui.transfer_dialog import TransferDialog, TransferItem


# ─── Mock TransferManager per i test della dialog ─────────────────────

class FakeTransferManager(QObject):
    """TransferManager fittizio che emette segnali per pilotare la dialog."""

    op_added = pyqtSignal(object)  # TransferOp
    op_progress = pyqtSignal(str, int, int, float)  # op_id, current, total, speed
    op_done = pyqtSignal(str, str, bool, str, str)  # op_id, op_type, success, msg, filename
    queue_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._queue = []
        self._current = None

    def get_queue(self):
        return self._queue.copy()

    def get_current(self):
        return self._current

    def emit_op_added(self, op: TransferOp):
        """Helper: emette op_added e aggiorna stato interno."""
        self._queue.append(op)
        self.op_added.emit(op)

    def emit_op_progress(self, op_id: str, current: int, total: int, speed: float = 0.0):
        self.op_progress.emit(op_id, current, total, speed)

    def emit_op_done(self, op_id: str, op_type: str, success: bool,
                     msg: str = "", filename: str = ""):
        self.op_done.emit(op_id, op_type, success, msg, filename)


@pytest.fixture
def fake_manager():
    return FakeTransferManager()


@pytest.fixture
def dialog(fake_manager, qtbot):
    dlg = TransferDialog(fake_manager)
    qtbot.addWidget(dlg)
    return dlg


# ─── Helpers per creare TransferOp di test ────────────────────────────

def make_upload_op(op_id="abc123", filename="test.txt", channel_id=-1001111111111, file_path="") -> TransferOp:
    return TransferOp(
        op_id=op_id, op_type="upload", channel_id=channel_id,
        file_path=file_path, filename=filename,
        status="queued"
    )


def make_download_op(op_id="xyz789", filename="remote.pdf", channel_id=-1001111111111,
                     message_id=12345) -> TransferOp:
    return TransferOp(
        op_id=op_id, op_type="download", channel_id=channel_id,
        message_id=message_id, file_path=f"/tmp/{filename}", filename=filename,
        status="queued"
    )


# ─── TransferDialog ───────────────────────────────────────────────────

class TestTransferDialogInit:
    """Test dell'inizializzazione della dialog."""

    def test_dialog_initial_state(self, dialog):
        """La dialog inizia con coda vuota."""
        assert dialog.total_ops == 0
        assert dialog.completed_ops == 0
        assert dialog.items == {}
        assert dialog.status_label.text() == "⏳ Coda vuota"

    def test_dialog_window_title(self, dialog):
        """La dialog ha il titolo corretto."""
        assert dialog.windowTitle() == "Trasferimenti"

    def test_dialog_minimum_size(self, dialog):
        """La dialog ha dimensioni minime."""
        assert dialog.minimumWidth() == 550
        assert dialog.minimumHeight() == 350

    def test_auto_clear_checked_by_default(self, dialog):
        """Il checkbox auto-clear è selezionato di default."""
        assert dialog.auto_clear_checkbox.isChecked()

    def test_dialog_has_clear_buttons(self, dialog):
        """La dialog ha i pulsanti Pulisci completati e Pulisci lista."""
        assert dialog.clear_btn is not None
        assert dialog.clear_all_btn is not None
        assert dialog.clear_btn.text() == "🧹 Pulisci completati"
        assert dialog.clear_all_btn.text() == "🗑 Pulisci lista"


class TestTransferDialogOps:
    """Test dell'aggiunta e completamento operazioni."""

    def test_op_added_creates_item(self, dialog, fake_manager):
        """Quando arriva una nuova operazione, viene creata una TransferItem."""
        op = make_upload_op(op_id="op1")
        fake_manager.emit_op_added(op)
        assert dialog.total_ops == 1
        assert "op1" in dialog.items

    def test_op_added_updates_status(self, dialog, fake_manager):
        """Lo stato si aggiorna quando arriva un'operazione."""
        op = make_upload_op(op_id="op1")
        fake_manager.emit_op_added(op)
        assert "completati" in dialog.status_label.text()

    def test_duplicate_op_ignored(self, dialog, fake_manager):
        """Operazione con lo stesso op_id viene ignorata."""
        op = make_upload_op(op_id="op1")
        fake_manager.emit_op_added(op)
        fake_manager.emit_op_added(op)  # Duplicato
        assert dialog.total_ops == 1

    def test_multiple_ops_increment_count(self, dialog, fake_manager):
        """Più operazioni incrementano il conteggio."""
        for i in range(3):
            fake_manager.emit_op_added(make_upload_op(op_id=f"op{i}"))
        assert dialog.total_ops == 3

    def test_op_progress_updates_item(self, dialog, fake_manager):
        """Il progresso di un'operazione aggiorna la TransferItem."""
        op = make_upload_op(op_id="op1")
        fake_manager.emit_op_added(op)
        fake_manager.emit_op_progress("op1", 50, 100, 2.5)
        item = dialog.items["op1"]
        assert item.total_bytes == 100
        assert "50%" in item.status_lbl.text() or item.status_lbl.text() == "⚡ 50%"

    def test_op_done_success(self, dialog, fake_manager):
        """Completamento con successo aggiorna l'item."""
        # Disabilita auto-clear per verificare lo stato dell'item
        dialog.auto_clear_checkbox.setChecked(False)
        op = make_upload_op(op_id="op1")
        fake_manager.emit_op_added(op)
        fake_manager.emit_op_done("op1", "upload", True, "/tmp/test.txt", "test.txt")
        item = dialog.items["op1"]
        assert "✅" in item.status_lbl.text()
        assert dialog.completed_ops == 1

    def test_op_done_failure(self, dialog, fake_manager):
        """Completamento con errore aggiorna l'item."""
        # Disabilita auto-clear per verificare lo stato dell'item
        dialog.auto_clear_checkbox.setChecked(False)
        op = make_upload_op(op_id="op1")
        fake_manager.emit_op_added(op)
        fake_manager.emit_op_done("op1", "upload", False, "Errore di rete", "test.txt")
        item = dialog.items["op1"]
        assert "❌" in item.status_lbl.text()

    def test_status_all_completed(self, dialog, fake_manager):
        """Quando tutte le operazioni sono completate, lo stato cambia."""
        # Disabilita auto-clear per verificare lo stato
        dialog.auto_clear_checkbox.setChecked(False)
        op = make_upload_op(op_id="op1")
        fake_manager.emit_op_added(op)
        fake_manager.emit_op_done("op1", "upload", True, "/tmp/test.txt", "test.txt")
        assert "Coda completata" in dialog.status_label.text()

    def test_status_in_progress(self, dialog, fake_manager):
        """Stato 'in corso' con operazioni pendenti."""
        fake_manager.emit_op_added(make_upload_op(op_id="op1"))
        fake_manager.emit_op_added(make_upload_op(op_id="op2"))
        fake_manager.emit_op_done("op1", "upload", True, "", "a.txt")
        assert "di" in dialog.status_label.text()
        assert "completati" in dialog.status_label.text()


class TestClearOperations:
    """Test della pulizia delle operazioni completate."""

    def test_clear_completed_removes_done_items(self, dialog, fake_manager):
        """_clear_completed rimuove gli item con ✅ o ❌."""
        # Disabilita auto-clear per accumulare gli item prima del clear manuale
        dialog.auto_clear_checkbox.setChecked(False)
        fake_manager.emit_op_added(make_upload_op(op_id="op1"))
        fake_manager.emit_op_added(make_upload_op(op_id="op2"))
        fake_manager.emit_op_done("op1", "upload", True, "", "a.txt")
        fake_manager.emit_op_done("op2", "upload", False, "err", "b.txt")

        assert dialog.total_ops == 2
        dialog._clear_completed()
        assert dialog.total_ops == 0
        assert len(dialog.items) == 0

    def test_clear_completed_keeps_running_items(self, dialog, fake_manager):
        """_clear_completed non rimuove item in corso."""
        fake_manager.emit_op_added(make_upload_op(op_id="op1"))
        fake_manager.emit_op_added(make_upload_op(op_id="op2"))
        fake_manager.emit_op_done("op1", "upload", True, "", "a.txt")

        dialog._clear_completed()
        # Solo op1 (done) rimosso, op2 (⏳) rimane
        assert dialog.total_ops == 1
        assert "op2" in dialog.items
        assert "op1" not in dialog.items

    def test_clear_all_removes_everything(self, dialog, fake_manager):
        """_clear_all rimuove TUTTI gli item, anche quelli in corso."""
        # Disabilita auto-clear per accumulare sia completati che in corso
        dialog.auto_clear_checkbox.setChecked(False)
        fake_manager.emit_op_added(make_upload_op(op_id="op1"))
        fake_manager.emit_op_added(make_upload_op(op_id="op2"))
        fake_manager.emit_op_done("op1", "upload", True, "", "a.txt")

        dialog._clear_all()
        assert dialog.total_ops == 0
        assert dialog.completed_ops == 0
        assert len(dialog.items) == 0

    def test_clear_button_clicks(self, dialog, fake_manager, qtbot):
        """Il pulsante Pulisci completati rimuove gli item done."""
        # Disabilita auto-clear per accumulare l'item
        dialog.auto_clear_checkbox.setChecked(False)
        fake_manager.emit_op_added(make_upload_op(op_id="op1"))
        fake_manager.emit_op_done("op1", "upload", True, "", "a.txt")
        assert dialog.total_ops == 1

        qtbot.mouseClick(dialog.clear_btn, Qt.MouseButton.LeftButton)
        qtbot.wait(100)
        assert dialog.total_ops == 0

    def test_clear_all_button_clicks(self, dialog, fake_manager, qtbot):
        """Il pulsante Pulisci lista rimuove tutti gli item."""
        fake_manager.emit_op_added(make_upload_op(op_id="op1"))
        fake_manager.emit_op_added(make_upload_op(op_id="op2"))
        assert dialog.total_ops == 2

        qtbot.mouseClick(dialog.clear_all_btn, Qt.MouseButton.LeftButton)
        qtbot.wait(100)
        assert dialog.total_ops == 0
        assert dialog.completed_ops == 0

    def test_auto_clear_triggers_on_done(self, dialog, fake_manager):
        """Con auto-clear attivo, l'item completato viene rimosso subito."""
        # _on_op_done chiama _clear_completed se auto_clear_checkbox è checked
        op = make_upload_op(op_id="op1")
        fake_manager.emit_op_added(op)
        fake_manager.emit_op_done("op1", "upload", True, "", "test.txt")
        # auto_clear_checkbox è checked di default → l'item viene rimosso
        assert dialog.total_ops == 0

    def test_auto_clear_disabled_keeps_item(self, dialog, fake_manager):
        """Con auto-clear disattivato, l'item completato rimane."""
        dialog.auto_clear_checkbox.setChecked(False)
        op = make_upload_op(op_id="op1")
        fake_manager.emit_op_added(op)
        fake_manager.emit_op_done("op1", "upload", True, "", "test.txt")
        assert dialog.total_ops == 1
        assert "op1" in dialog.items


# ─── TransferItem ─────────────────────────────────────────────────────

class TestTransferItem:
    """Test del widget TransferItem isolato."""

    def test_item_creation_upload(self, qtbot):
        """TransferItem per upload viene creato con icona ⬆."""
        op = make_upload_op(op_id="up1", filename="report.pdf")
        item = TransferItem(op)
        qtbot.addWidget(item)
        assert item.op_id == "up1"
        assert item.op_type == "upload"
        assert item.filename == "report.pdf"
        assert item.icon_lbl.text() == "⬆"

    def test_item_creation_download(self, qtbot):
        """TransferItem per download viene creato con icona ⬇."""
        op = make_download_op(op_id="dl1", filename="remote.pdf")
        item = TransferItem(op)
        qtbot.addWidget(item)
        assert item.op_id == "dl1"
        assert item.op_type == "download"
        assert item.icon_lbl.text() == "⬇"

    def test_item_initial_state(self, qtbot):
        """TransferItem appena creato mostra stato 'In attesa'."""
        op = make_upload_op(op_id="op1")
        item = TransferItem(op)
        qtbot.addWidget(item)
        assert item.info_lbl.text() == "In attesa..."
        assert item.progress.value() == 0
        assert item.progress.maximum() == 100

    def test_item_progress_with_total(self, qtbot):
        """set_progress con total > 0 aggiorna la progress bar."""
        op = make_upload_op(op_id="op1")
        item = TransferItem(op)
        qtbot.addWidget(item)
        item.set_progress(50, 100, speed_mb_s=1.5)
        assert item.total_bytes == 100
        assert item.progress.maximum() == 100
        assert item.progress.value() == 50
        assert "50%" in item.status_lbl.text()

    def test_item_progress_without_total(self, qtbot):
        """set_progress con total = 0 mostra solo l'indicatore di attività."""
        op = make_upload_op(op_id="op1")
        item = TransferItem(op)
        qtbot.addWidget(item)
        item.set_progress(0, 0, speed_mb_s=0.5)
        assert item.status_lbl.text() == "⚡"

    def test_item_mark_done_success(self, qtbot):
        """mark_done con success=True mostra ✅ e barra verde."""
        op = make_upload_op(op_id="op1")
        item = TransferItem(op)
        qtbot.addWidget(item)
        item.mark_done(True, "")
        assert "✅" in item.status_lbl.text()
        assert item.progress.value() == 100

    def test_item_mark_done_failure(self, qtbot):
        """mark_done con success=False mostra ❌ e barra rossa."""
        op = make_upload_op(op_id="op1")
        item = TransferItem(op)
        qtbot.addWidget(item)
        item.mark_done(False, "File non trovato")
        assert "❌" in item.status_lbl.text()
        assert item.progress.value() == 0

    def test_item_running_state(self, qtbot):
        """TransferOp con status='running' mostra ⚡ all'avvio."""
        op = make_upload_op(op_id="op1")
        op.status = "running"
        item = TransferItem(op)
        qtbot.addWidget(item)
        assert "⚡" in item.status_lbl.text()

    def test_item_error_state(self, qtbot):
        """TransferOp con status='error' mostra ❌ all'avvio."""
        op = make_upload_op(op_id="op1")
        op.status = "error"
        op.error_msg = "Timeout"
        item = TransferItem(op)
        qtbot.addWidget(item)
        assert "❌" in item.status_lbl.text()

    def test_item_done_state(self, qtbot):
        """TransferOp con status='done' mostra ✅ all'avvio."""
        op = make_upload_op(op_id="op1")
        op.status = "done"
        item = TransferItem(op)
        qtbot.addWidget(item)
        assert "✅" in item.status_lbl.text()

    def test_item_tooltip_has_channel_info(self, qtbot):
        """Il tooltip della progress bar mostra l'ID del canale."""
        op = make_upload_op(op_id="op1", channel_id=-1001234567890)
        item = TransferItem(op)
        qtbot.addWidget(item)
        assert "Canale: -1001234567890" in item.progress.toolTip()

    def test_item_channel_info_in_format(self, qtbot):
        """L'info canale appare nel formato della progress bar."""
        op = make_upload_op(op_id="op1", channel_id=-1001234567890)
        item = TransferItem(op)
        qtbot.addWidget(item)
        fmt = item.progress.format()
        assert "%p%" in fmt
        assert item.filename in fmt
