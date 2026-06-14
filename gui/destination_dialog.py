from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel
)
from PyQt6.QtCore import Qt
from database import Database


class DestinationDialog(QDialog):
    """Dialog per selezionare un canale di destinazione per copia/sposta file."""

    def __init__(self, db: Database, parent=None, action: str = "copy",
                 exclude_channel_ids: set = None):
        super().__init__(parent)
        self.db = db
        self.action = action  # "copy" or "move"
        self.selected_channel_id = None
        self._build_ui()
        self._load_channels(exclude_channel_ids or set())

    def _build_ui(self):
        self.setWindowTitle(
            "📋 Copia file in un altro canale" if self.action == "copy"
            else "📦 Sposta file in un altro canale"
        )
        self.setMinimumSize(380, 320)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        label = QLabel("Seleziona il canale di destinazione:")
        layout.addWidget(label)

        self.channel_list = QListWidget()
        self.channel_list.setAlternatingRowColors(True)
        layout.addWidget(self.channel_list)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_text = "📋 Copia qui" if self.action == "copy" else "📦 Sposta qui"
        self.btn_ok = QPushButton(btn_text)
        self.btn_ok.setEnabled(False)
        self.btn_ok.clicked.connect(self._on_ok)
        btn_cancel = QPushButton("Annulla")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

        self.channel_list.itemSelectionChanged.connect(
            lambda: self.btn_ok.setEnabled(
                len(self.channel_list.selectedItems()) > 0
            )
        )
        self.channel_list.itemDoubleClicked.connect(self._on_ok)

    def _load_channels(self, exclude_ids: set):
        favs = self.db.get_favorite_channels()
        count = 0
        for ch in favs:
            if ch['channel_id'] in exclude_ids:
                continue
            item = QListWidgetItem(f"📁 {ch['display_name']}")
            item.setData(Qt.ItemDataRole.UserRole, ch['channel_id'])
            self.channel_list.addItem(item)
            count += 1
        if count == 0:
            placeholder = QListWidgetItem("Nessun canale di destinazione disponibile")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self.channel_list.addItem(placeholder)

    def _on_ok(self):
        item = self.channel_list.currentItem()
        if item:
            self.selected_channel_id = item.data(Qt.ItemDataRole.UserRole)
            self.accept()
