from PyQt6.QtCore import QAbstractTableModel, Qt, QModelIndex, QMimeData
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QStyledItemDelegate, QComboBox
import json
from typing import List, Dict, Tuple, Set, Optional
from database import FileRecord


class TagDelegate(QStyledItemDelegate):
    """Delegate che mostra un QComboBox per la colonna Tags."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tags: List[str] = [""]

    def set_tags(self, tags: List[str]):
        """Aggiorna la lista dei tag disponibili (incluso stringa vuota per 'nessun tag')."""
        self._tags = [""] + sorted(tags)

    def createEditor(self, parent, option, index):
        combo = QComboBox(parent)
        combo.addItems(self._tags)
        combo.currentTextChanged.connect(lambda: self.commitData.emit(combo))
        return combo

    def setEditorData(self, editor, index):
        current = index.data(Qt.ItemDataRole.DisplayRole) or ""
        idx = editor.findText(current)
        if idx >= 0:
            editor.setCurrentIndex(idx)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)


class CloudFileModel(QAbstractTableModel):
    CHECKBOX_COL = 0
    COLUMNS = ["", "Nome", "Dimensione", "Tipo", "Data", "Canale", "Tags"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._files: List[FileRecord] = []
        self._channel_names: dict = {}
        self._transfers: List[Tuple[str, FileRecord]] = []
        self._transfer_status: Dict[str, str] = {}
        self._transfer_op_type: Dict[str, str] = {}
        self._checked: Set[int] = set()  # indices into _files

    def set_files(self, files: List[FileRecord]):
        self.beginResetModel()
        self._files = files
        self._checked.clear()
        self.endResetModel()

    def set_channel_names(self, names: dict):
        self._channel_names = names
        self.layoutChanged.emit()

    def add_transfer(self, op_id: str, filename: str, size: int, mime_type: str, channel_id: int, op_type: str = "upload"):
        self.beginInsertRows(QModelIndex(), 0, 0)
        record = FileRecord(
            id=-1,
            message_id=-1,
            filename=filename,
            size=size,
            mime_type=mime_type,
            upload_date="⬆ In upload..." if op_type == "upload" else "⬇ In download...",
            tags="",
            local_path=None,
            telegram_path=None,
            channel_id=channel_id,
        )
        self._transfers.insert(0, (op_id, record))
        self._transfer_status[op_id] = "running"
        self._transfer_op_type[op_id] = op_type
        self.endInsertRows()

    def remove_transfer(self, op_id: str):
        for idx, (oid, _) in enumerate(self._transfers):
            if oid == op_id:
                self.beginRemoveRows(QModelIndex(), idx, idx)
                self._transfers.pop(idx)
                self._transfer_status.pop(op_id, None)
                self._transfer_op_type.pop(op_id, None)
                self.endRemoveRows()
                return

    # ── Checkbox API ──────────────────────────────────────────────

    def get_checked_files(self) -> List[FileRecord]:
        """Restituisce i file con checkbox selezionata."""
        return [self._files[i] for i in sorted(self._checked) if i < len(self._files)]

    def checked_count(self) -> int:
        return len(self._checked)

    def file_count(self) -> int:
        """Numero totale di file (esclusi i transfer in corso)."""
        return len(self._files)

    def check_all(self):
        """Seleziona tutte le righe (solo file, non transfer)."""
        self._checked = set(range(len(self._files)))
        top_left = self.index(len(self._transfers), self.CHECKBOX_COL)
        bottom_right = self.index(self.rowCount() - 1, self.CHECKBOX_COL)
        self.dataChanged.emit(top_left, bottom_right, [Qt.ItemDataRole.CheckStateRole])
        self.headerDataChanged.emit(Qt.Orientation.Horizontal, self.CHECKBOX_COL, self.CHECKBOX_COL)

    def uncheck_all(self):
        """Deseleziona tutte le righe."""
        self._checked.clear()
        top_left = self.index(len(self._transfers), self.CHECKBOX_COL)
        bottom_right = self.index(self.rowCount() - 1, self.CHECKBOX_COL)
        self.dataChanged.emit(top_left, bottom_right, [Qt.ItemDataRole.CheckStateRole])
        self.headerDataChanged.emit(Qt.Orientation.Horizontal, self.CHECKBOX_COL, self.CHECKBOX_COL)

    def toggle_all(self):
        """Toggle tra seleziona tutto e deseleziona tutto."""
        if len(self._checked) == len(self._files) and len(self._files) > 0:
            self.uncheck_all()
        else:
            self.check_all()

    def is_all_checked(self) -> bool:
        return len(self._files) > 0 and len(self._checked) == len(self._files)

    # ── Qt Model methods ─────────────────────────────────────────

    def supportedDragActions(self):
        return Qt.DropAction.CopyAction

    def mimeData(self, indexes):
        mime_data = QMimeData()
        rows = set()
        files = []
        for idx in indexes:
            if idx.isValid() and idx.row() not in rows:
                rows.add(idx.row())
                file = self.get_file(idx)
                if file and file.message_id > 0:
                    files.append({
                        "message_id": file.message_id,
                        "filename": file.filename,
                        "channel_id": file.channel_id,
                        "original_filename": file.original_filename,
                    })
        if files:
            mime_data.setData("application/x-tgmdrive-cloud-file", json.dumps(files).encode())
        return mime_data

    def get_file(self, index: QModelIndex) -> FileRecord:
        row = index.row()
        if row < len(self._transfers):
            return self._transfers[row][1]
        return self._files[row - len(self._transfers)]

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        base = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        # Checkbox column: NON usiamo ItemIsUserCheckable per evitare conflitti
        # col delegate Qt. Il toggle è gestito manualmente via clicked signal.
        if index.column() == self.CHECKBOX_COL:
            return base
        if index.row() >= len(self._transfers):
            base |= Qt.ItemFlag.ItemIsDragEnabled
        # Rendi la colonna Tags editabile (colonna 6)
        if index.column() == 6:
            base |= Qt.ItemFlag.ItemIsEditable
        return base

    def rowCount(self, parent=QModelIndex()):
        return len(self._files) + len(self._transfers)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal:
            if section == self.CHECKBOX_COL and role == Qt.ItemDataRole.DisplayRole:
                if self.is_all_checked():
                    return "☑"
                if len(self._checked) > 0:
                    return "◐"
                return "☐"
            if role == Qt.ItemDataRole.DisplayRole:
                return self.COLUMNS[section]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= self.rowCount():
            return None
        row = index.row()
        is_transfer = row < len(self._transfers)
        if is_transfer:
            op_id, file = self._transfers[row]
        else:
            file = self._files[row - len(self._transfers)]
        col = index.column()

        # Checkbox column
        if col == self.CHECKBOX_COL:
            if role == Qt.ItemDataRole.CheckStateRole:
                if is_transfer:
                    return None
                file_idx = row - len(self._transfers)
                return Qt.CheckState.Checked if file_idx in self._checked else Qt.CheckState.Unchecked
            return None

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 1:  # Nome
                prefix = ""
                if is_transfer:
                    prefix = "⬆ " if self._transfer_op_type.get(op_id, "upload") == "upload" else "⬇ "
                display_name = file.original_filename or file.filename
                return prefix + display_name
            if col == 2:  # Dimensione
                return self.format_size(file.size)
            if col == 3:  # Tipo
                return file.mime_type
            if col == 4:  # Data
                return file.upload_date
            if col == 5:  # Canale
                return self._channel_names.get(file.channel_id, str(file.channel_id))
            if col == 6:  # Tags
                return file.tags

        if role == Qt.ItemDataRole.FontRole and is_transfer and col == 1:
            font = QFont()
            font.setItalic(True)
            return font

        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if role == Qt.ItemDataRole.CheckStateRole and index.column() == self.CHECKBOX_COL:
            row = index.row()
            if row < len(self._transfers):
                return False
            file_idx = row - len(self._transfers)
            if value == Qt.CheckState.Checked:
                self._checked.add(file_idx)
            else:
                self._checked.discard(file_idx)
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
            self.headerDataChanged.emit(Qt.Orientation.Horizontal, self.CHECKBOX_COL, self.CHECKBOX_COL)
            return True
        if role == Qt.ItemDataRole.EditRole and index.column() == 6:
            row = index.row()
            if row < len(self._transfers):
                return False
            file = self._files[row - len(self._transfers)]
            new_tag = str(value) if value else ""
            file.tags = new_tag
            self.dataChanged.emit(index, index, [role])
            return True
        return False

    # ── Utility ──────────────────────────────────────────────────

    def format_size(self, size: int) -> str:
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        if size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        return f"{size / (1024 * 1024 * 1024):.1f} GB"
