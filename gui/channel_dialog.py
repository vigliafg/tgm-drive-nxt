from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QMessageBox, QProgressBar,
    QLineEdit, QGroupBox
)
from PyQt6.QtCore import Qt

from telegram_client import TelegramClientThread


class ChannelDialog(QDialog):
    def __init__(self, tg_client: TelegramClientThread, parent=None):
        super().__init__(parent)
        self.tg_client = tg_client
        self.selected_channel_id = None
        self.selected_channel_name = ""
        self.setWindowTitle("Seleziona Canale Telegram")
        self.setMinimumWidth(450)
        self.setMinimumHeight(300)
        self._build_ui()
        self._connect_signals()
        self.tg_client.list_channels()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        info = QLabel(
            "Seleziona un canale esistente tra quelli di cui sei amministratore.\n"
            "L'ID verrà configurato automaticamente."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Cerca canale...")
        layout.addWidget(self.search_edit)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(True)
        layout.addWidget(self.progress)

        # Fallback manuale
        manual_box = QGroupBox("Oppure inserisci l'ID manualmente")
        manual_layout = QHBoxLayout(manual_box)
        self.manual_edit = QLineEdit()
        self.manual_edit.setPlaceholderText("es. -1001234567890")
        self.manual_btn = QPushButton("Usa ID")
        manual_layout.addWidget(self.manual_edit, stretch=1)
        manual_layout.addWidget(self.manual_btn)
        layout.addWidget(manual_box)

        btn_layout = QHBoxLayout()
        self.select_btn = QPushButton("Seleziona")
        self.select_btn.setEnabled(False)
        self.cancel_btn = QPushButton("Annulla")
        btn_layout.addStretch()
        btn_layout.addWidget(self.select_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

    def _connect_signals(self):
        self.select_btn.clicked.connect(self._on_select)
        self.cancel_btn.clicked.connect(self.reject)
        self.list_widget.itemDoubleClicked.connect(self._on_select)
        self.manual_btn.clicked.connect(self._on_manual)
        self.manual_edit.returnPressed.connect(self._on_manual)
        self.search_edit.textChanged.connect(self._on_search)
        self.tg_client.channels_ready.connect(self._on_channels_ready)
        self.tg_client.error_occurred.connect(self._on_error)

    def _on_channels_ready(self, channels: list):
        self.progress.setVisible(False)
        self.all_channels = sorted(channels, key=lambda x: x.get('title', '').lower())
        self._filter_channels("")
        if channels:
            self.setWindowTitle(f"Seleziona Canale Telegram ({len(channels)} trovati)")

    def _filter_channels(self, query: str):
        self.list_widget.clear()
        q = query.lower()
        visible = []
        for ch in self.all_channels:
            if q in ch.get('title', '').lower() or q in (ch.get('username', '') or '').lower():
                visible.append(ch)
        if not visible:
            item = QListWidgetItem("Nessun canale corrispondente")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list_widget.addItem(item)
            self.select_btn.setEnabled(False)
            return
        for ch in visible:
            display = f"{ch['title']}"
            if ch['username']:
                display += f" (@{ch['username']})"
            display += f" — ID: {ch['id']}"
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, ch['id'])
            self.list_widget.addItem(item)
        self.select_btn.setEnabled(True)

    def _on_error(self, msg: str):
        self.progress.setVisible(False)
        QMessageBox.critical(self, "Errore", f"Impossibile caricare i canali:\n{msg}")

    def _on_select(self):
        item = self.list_widget.currentItem()
        if item and item.flags() & Qt.ItemFlag.ItemIsEnabled:
            self.selected_channel_id = item.data(Qt.ItemDataRole.UserRole)
            self.selected_channel_name = item.text().split(" — ID:")[0].strip()
            self.accept()
        else:
            QMessageBox.warning(self, "Errore", "Seleziona un canale dalla lista")

    def _on_manual(self):
        text = self.manual_edit.text().strip()
        if not text:
            QMessageBox.warning(self, "Errore", "Inserisci un ID")
            return
        try:
            self.selected_channel_id = int(text)
            self.selected_channel_name = f"Canale {text}"
            self.accept()
        except ValueError:
            QMessageBox.warning(self, "Errore", "ID non valido")

    def _on_search(self, text: str):
        if not hasattr(self, 'all_channels'):
            return
        self._filter_channels(text)
