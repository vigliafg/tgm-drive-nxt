import json
from typing import List, Dict, Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QTabWidget, QWidget, QLabel, QLineEdit,
    QPushButton, QSpinBox, QComboBox, QMessageBox,
    QListWidget, QListWidgetItem, QGroupBox,
    QSplitter, QFrame, QFileDialog, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal

from config import save_config, CONFIG_FILE
from database import Database


class FavoriteChannelsTab(QWidget):
    """Tab per gestire i canali preferiti all'interno del SettingsDialog."""

    channels_changed = pyqtSignal()

    def __init__(self, db: Database, tg_client, parent=None):
        super().__init__(parent)
        self.db = db
        self.tg_client = tg_client
        self._all_telegram_channels: List[Dict] = []
        self._favorite_channels: List[Dict] = []
        self._build_ui()
        self._load_favorites()
        self._load_telegram_channels()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(8, 8, 8, 8)

        # Left: All Telegram channels list
        left_box = QGroupBox("📡 Tutti i Canali Telegram")
        left_layout = QVBoxLayout(left_box)
        self.all_list = QListWidget()
        self.all_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        left_layout.addWidget(self.all_list)

        self.refresh_btn = QPushButton("🔄 Aggiorna lista")
        left_layout.addWidget(self.refresh_btn)

        # Center: action buttons
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.btn_add = QPushButton("➕ Aggiungi →")
        self.btn_add.setMinimumWidth(120)
        center_layout.addWidget(self.btn_add)
        center_layout.addStretch()

        # Right: Favorite channels list
        right_box = QGroupBox("⭐ Canali Preferiti")
        right_layout = QVBoxLayout(right_box)
        self.fav_list = QListWidget()
        self.fav_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.fav_list.itemDoubleClicked.connect(self._on_rename_favorite)
        right_layout.addWidget(self.fav_list)

        right_btn_layout = QHBoxLayout()
        self.btn_up = QPushButton("⬆ Su")
        self.btn_down = QPushButton("⬇ Giù")
        self.btn_rename = QPushButton("✏️ Rinomina")
        self.btn_remove = QPushButton("➖ Rimuovi")
        right_btn_layout.addWidget(self.btn_up)
        right_btn_layout.addWidget(self.btn_down)
        right_btn_layout.addWidget(self.btn_rename)
        right_btn_layout.addWidget(self.btn_remove)
        right_layout.addLayout(right_btn_layout)

        layout.addWidget(left_box, stretch=1)
        layout.addWidget(center_widget)
        layout.addWidget(right_box, stretch=1)

        # Connect signals
        self.btn_add.clicked.connect(self._on_add)
        self.btn_remove.clicked.connect(self._on_remove)
        self.btn_rename.clicked.connect(self._on_rename_favorite)
        self.btn_up.clicked.connect(self._on_move_up)
        self.btn_down.clicked.connect(self._on_move_down)
        self.refresh_btn.clicked.connect(self._load_telegram_channels)
        self.tg_client.channels_ready.connect(self._on_telegram_channels_ready)
        self.tg_client.error_occurred.connect(self._on_telegram_error)

    def _load_favorites(self):
        self._favorite_channels = self.db.get_favorite_channels()
        self._refresh_fav_list()

    def _refresh_fav_list(self):
        self.fav_list.clear()
        for ch in self._favorite_channels:
            display = f"{ch['display_name']} (ID: {ch['channel_id']})"
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, ch)
            self.fav_list.addItem(item)

    def _load_telegram_channels(self):
        self.all_list.clear()
        item = QListWidgetItem("Caricamento...")
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        self.all_list.addItem(item)
        self.tg_client.list_channels()

    def _on_telegram_channels_ready(self, channels: List[Dict]):
        self._all_telegram_channels = sorted(channels, key=lambda x: x.get('title', '').lower())
        self.all_list.clear()
        if not self._all_telegram_channels:
            item = QListWidgetItem("Nessun canale trovato")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.all_list.addItem(item)
            return
        # Filter out already-favorite channels
        fav_ids = {ch['channel_id'] for ch in self._favorite_channels}
        for ch in self._all_telegram_channels:
            if ch['id'] in fav_ids:
                continue
            display = f"{ch['title']}"
            if ch.get('username'):
                display += f" (@{ch['username']})"
            display += f" — ID: {ch['id']}"
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, ch)
            self.all_list.addItem(item)

    def _on_telegram_error(self, msg: str):
        self.all_list.clear()
        item = QListWidgetItem(f"Errore: {msg}")
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        self.all_list.addItem(item)

    def _on_add(self):
        item = self.all_list.currentItem()
        if not item or not item.flags() & Qt.ItemFlag.ItemIsEnabled:
            return
        ch = item.data(Qt.ItemDataRole.UserRole)
        if not ch:
            return
        new_fav = {
            "channel_id": ch['id'],
            "channel_name": ch['title'],
            "display_name": ch['title'],
            "sort_order": len(self._favorite_channels),
        }
        self._favorite_channels.append(new_fav)
        self._refresh_fav_list()
        self._on_telegram_channels_ready(self._all_telegram_channels)
        self.channels_changed.emit()

    def _on_remove(self):
        item = self.fav_list.currentItem()
        if not item:
            return
        idx = self.fav_list.row(item)
        self._favorite_channels.pop(idx)
        # Rebuild sort_order
        for i, ch in enumerate(self._favorite_channels):
            ch['sort_order'] = i
        self._refresh_fav_list()
        self._on_telegram_channels_ready(self._all_telegram_channels)
        self.channels_changed.emit()

    def _on_move_up(self):
        idx = self.fav_list.currentRow()
        if idx <= 0:
            return
        self._favorite_channels[idx], self._favorite_channels[idx - 1] = (
            self._favorite_channels[idx - 1], self._favorite_channels[idx]
        )
        for i, ch in enumerate(self._favorite_channels):
            ch['sort_order'] = i
        self._refresh_fav_list()
        self.fav_list.setCurrentRow(idx - 1)
        self.channels_changed.emit()

    def _on_move_down(self):
        idx = self.fav_list.currentRow()
        if idx < 0 or idx >= len(self._favorite_channels) - 1:
            return
        self._favorite_channels[idx], self._favorite_channels[idx + 1] = (
            self._favorite_channels[idx + 1], self._favorite_channels[idx]
        )
        for i, ch in enumerate(self._favorite_channels):
            ch['sort_order'] = i
        self._refresh_fav_list()
        self.fav_list.setCurrentRow(idx + 1)
        self.channels_changed.emit()

    def _on_rename_favorite(self):
        item = self.fav_list.currentItem()
        if not item:
            return
        idx = self.fav_list.row(item)
        ch = self._favorite_channels[idx]
        from PyQt6.QtWidgets import QInputDialog
        new_name, ok = QInputDialog.getText(
            self, "Rinomina canale", "Nuovo nome visualizzato:", text=ch['display_name']
        )
        if ok and new_name.strip():
            ch['display_name'] = new_name.strip()
            self._refresh_fav_list()
            self.db.update_favorite_channel_display_name(ch['channel_id'], ch['display_name'])
            self.channels_changed.emit()

    def get_favorite_channels(self) -> List[Dict]:
        return self._favorite_channels

    def save_to_db(self):
        self.db.set_favorite_channels(self._favorite_channels)


class TagsTab(QWidget):
    """Tab per gestire i tag all'interno del SettingsDialog."""

    tags_changed = pyqtSignal()

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self._tags: List[Dict] = []
        self._build_ui()
        self._load_tags()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        # Input per nuovo tag
        input_layout = QHBoxLayout()
        self.new_tag_edit = QLineEdit()
        self.new_tag_edit.setPlaceholderText("Nome del nuovo tag...")
        self.new_tag_edit.returnPressed.connect(self._on_add_tag)
        input_layout.addWidget(self.new_tag_edit, stretch=1)
        self.btn_add = QPushButton("➕ Aggiungi")
        self.btn_add.clicked.connect(self._on_add_tag)
        input_layout.addWidget(self.btn_add)
        layout.addLayout(input_layout)

        # Lista tag con controlli
        group = QGroupBox("🏷️ Tag Disponibili")
        group_layout = QVBoxLayout(group)

        self.tag_list = QListWidget()
        self.tag_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.tag_list.itemDoubleClicked.connect(self._on_rename_tag)
        group_layout.addWidget(self.tag_list)

        btn_layout = QHBoxLayout()
        self.btn_rename = QPushButton("✏️ Rinomina")
        self.btn_rename.clicked.connect(self._on_rename_tag)
        self.btn_remove = QPushButton("➖ Rimuovi")
        self.btn_remove.clicked.connect(self._on_remove_tag)
        self.btn_up = QPushButton("⬆ Su")
        self.btn_up.clicked.connect(self._on_move_up)
        self.btn_down = QPushButton("⬇ Giù")
        self.btn_down.clicked.connect(self._on_move_down)
        btn_layout.addWidget(self.btn_rename)
        btn_layout.addWidget(self.btn_remove)
        btn_layout.addWidget(self.btn_up)
        btn_layout.addWidget(self.btn_down)
        btn_layout.addStretch()
        group_layout.addLayout(btn_layout)

        layout.addWidget(group)

        # Info conteggio
        self.info_label = QLabel("")
        self.info_label.setStyleSheet("color: #888; font-style: italic;")
        layout.addWidget(self.info_label)
        layout.addStretch()

    def _load_tags(self):
        self._tags = self.db.get_tags()
        self._refresh_list()

    def _refresh_list(self):
        self.tag_list.clear()
        for t in self._tags:
            count = len(self.db.get_files_by_tag(t['tag_name']))
            display = f"{t['tag_name']}  ({count} file)"
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, t)
            self.tag_list.addItem(item)
        self.info_label.setText(f"{len(self._tags)} tag disponibili")

    def _on_add_tag(self):
        name = self.new_tag_edit.text().strip()
        if not name:
            return
        if any(t['tag_name'].lower() == name.lower() for t in self._tags):
            QMessageBox.warning(self, "Attenzione", f"Il tag '{name}' esiste già.")
            return
        new_tag = {"tag_id": -1, "tag_name": name, "sort_order": len(self._tags)}
        self._tags.append(new_tag)
        self._refresh_list()
        self.new_tag_edit.clear()
        self.tags_changed.emit()

    def _on_remove_tag(self):
        item = self.tag_list.currentItem()
        if not item:
            return
        idx = self.tag_list.row(item)
        tag = self._tags[idx]
        count = len(self.db.get_files_by_tag(tag['tag_name']))
        if count > 0:
            reply = QMessageBox.question(
                self, "Conferma",
                f"Il tag '{tag['tag_name']}' è usato da {count} file.\n"
                f"Rimuovendolo, verrà rimosso da tutti i file. Continuare?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self._tags.pop(idx)
        for i, t in enumerate(self._tags):
            t['sort_order'] = i
        self._refresh_list()
        self.tags_changed.emit()

    def _on_rename_tag(self):
        item = self.tag_list.currentItem()
        if not item:
            return
        idx = self.tag_list.row(item)
        tag = self._tags[idx]
        new_name, ok = QInputDialog.getText(
            self, "Rinomina tag", "Nuovo nome del tag:", text=tag['tag_name']
        )
        if ok and new_name.strip() and new_name.strip() != tag['tag_name']:
            new_name = new_name.strip()
            if any(t['tag_name'].lower() == new_name.lower() for t in self._tags):
                QMessageBox.warning(self, "Attenzione", f"Il tag '{new_name}' esiste già.")
                return
            tag['tag_name'] = new_name
            self._refresh_list()
            self.tags_changed.emit()

    def _on_move_up(self):
        idx = self.tag_list.currentRow()
        if idx <= 0:
            return
        self._tags[idx], self._tags[idx - 1] = self._tags[idx - 1], self._tags[idx]
        for i, t in enumerate(self._tags):
            t['sort_order'] = i
        self._refresh_list()
        self.tag_list.setCurrentRow(idx - 1)
        self.tags_changed.emit()

    def _on_move_down(self):
        idx = self.tag_list.currentRow()
        if idx < 0 or idx >= len(self._tags) - 1:
            return
        self._tags[idx], self._tags[idx + 1] = self._tags[idx + 1], self._tags[idx]
        for i, t in enumerate(self._tags):
            t['sort_order'] = i
        self._refresh_list()
        self.tag_list.setCurrentRow(idx + 1)
        self.tags_changed.emit()

    def get_tags(self) -> List[Dict]:
        return self._tags

    def save_to_db(self):
        """Salva tutti i tag nel DB. Gestisce rinomine e nuove aggiunte."""
        existing = {t['tag_name']: t for t in self.db.get_tags()}
        for new_tag in self._tags:
            if new_tag['tag_id'] > 0:
                for old_name, old_tag in existing.items():
                    if old_tag['tag_id'] == new_tag['tag_id'] and old_name != new_tag['tag_name']:
                        self.db.rename_tag(new_tag['tag_id'], new_tag['tag_name'])
                        break
        self.db.set_tags(self._tags)


class SettingsDialog(QDialog):
    """Dialog impostazioni con 4 tab: UI, Telegram, Canali Preferiti, Tags."""

    TAB_UI = 0
    TAB_TELEGRAM = 1
    TAB_FAVORITES = 2
    TAB_TAGS = 3

    settings_applied = pyqtSignal(dict)
    reconnect_requested = pyqtSignal()
    disconnect_requested = pyqtSignal()

    def __init__(self, config: dict, db: Database, tg_client, parent=None, initial_tab: int = 0):
        super().__init__(parent)
        self.config = config
        self.db = db
        self.tg_client = tg_client
        self._initial_tab = initial_tab
        self.setWindowTitle("⚙️ Impostazioni")
        self.setMinimumWidth(650)
        self.setMinimumHeight(500)
        self._build_ui()
        self._load_settings()
        self.tabs.setCurrentIndex(self._initial_tab)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        self.tabs = QTabWidget()

        # Tab 1: UI Settings
        self.tab_ui = QWidget()
        self._build_ui_tab()
        self.tabs.addTab(self.tab_ui, "🎨 UI")

        # Tab 2: Telegram Settings
        self.tab_telegram = QWidget()
        self._build_telegram_tab()
        self.tabs.addTab(self.tab_telegram, "📡 Telegram")

        # Tab 3: Favorite Channels
        self.tab_favorites = FavoriteChannelsTab(self.db, self.tg_client)
        self.tabs.addTab(self.tab_favorites, "⭐ Canali Preferiti")

        # Tab 4: Tags
        self.tab_tags = TagsTab(self.db)
        self.tabs.addTab(self.tab_tags, "🏷️ Tags")

        layout.addWidget(self.tabs, stretch=1)

        # Bottom buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.save_btn = QPushButton("💾 Salva")
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self._on_save)
        self.cancel_btn = QPushButton("❌ Annulla")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

    def _build_ui_tab(self):
        layout = QVBoxLayout(self.tab_ui)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        form = QFormLayout()
        form.setSpacing(8)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark", "Light", "System"])
        form.addRow("Tema:", self.theme_combo)

        self.font_spin = QSpinBox()
        self.font_spin.setRange(8, 24)
        self.font_spin.setSuffix(" pt")
        form.addRow("Dimensione font:", self.font_spin)

        self.win_width_spin = QSpinBox()
        self.win_width_spin.setRange(800, 3840)
        self.win_width_spin.setSuffix(" px")
        form.addRow("Larghezza finestra:", self.win_width_spin)

        self.win_height_spin = QSpinBox()
        self.win_height_spin.setRange(600, 2160)
        self.win_height_spin.setSuffix(" px")
        form.addRow("Altezza finestra:", self.win_height_spin)

        self.auto_clear_checkbox = QComboBox()
        self.auto_clear_checkbox.addItems(["Sì", "No"])
        form.addRow("Pulisci completati automaticamente:", self.auto_clear_checkbox)

        layout.addLayout(form)
        layout.addStretch()

    def _build_telegram_tab(self):
        layout = QVBoxLayout(self.tab_telegram)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        form = QFormLayout()
        form.setSpacing(8)

        self.api_id_edit = QLineEdit()
        self.api_id_edit.setPlaceholderText("12345")
        form.addRow("API ID:", self.api_id_edit)

        self.api_hash_edit = QLineEdit()
        self.api_hash_edit.setPlaceholderText("abc123...")
        form.addRow("API Hash:", self.api_hash_edit)

        self.phone_edit = QLineEdit()
        self.phone_edit.setPlaceholderText("+39333...")
        form.addRow("Phone:", self.phone_edit)

        layout.addLayout(form)

        # Session status
        status_box = QGroupBox("Stato sessione")
        status_layout = QHBoxLayout(status_box)
        self.status_lbl = QLabel("❌ Non connesso")
        if self.tg_client.is_connected():
            self.status_lbl.setText("✅ Connesso")
        status_layout.addWidget(self.status_lbl)
        status_layout.addStretch()

        self.btn_disconnect = QPushButton("🔌 Disconnetti")
        self.btn_disconnect.clicked.connect(self._on_disconnect)
        self.btn_reconnect = QPushButton("🔄 Riconnetti")
        self.btn_reconnect.clicked.connect(self._on_reconnect)
        status_layout.addWidget(self.btn_disconnect)
        status_layout.addWidget(self.btn_reconnect)
        layout.addWidget(status_box)

        layout.addStretch()

    def _load_settings(self):
        # UI
        theme = self.config.get("ui_theme", "dark")
        idx = self.theme_combo.findText(theme.capitalize())
        if idx >= 0:
            self.theme_combo.setCurrentIndex(idx)
        self.font_spin.setValue(self.config.get("ui_font_size", 11))
        self.win_width_spin.setValue(self.config.get("window_width", 1200))
        self.win_height_spin.setValue(self.config.get("window_height", 700))
        auto_clear = self.config.get("auto_clear_transfers", True)
        self.auto_clear_checkbox.setCurrentIndex(0 if auto_clear else 1)

        # Telegram
        self.api_id_edit.setText(self.config.get("api_id", ""))
        self.api_hash_edit.setText(self.config.get("api_hash", ""))
        self.phone_edit.setText(self.config.get("phone", ""))

    def _on_save(self):
        # UI
        self.config["ui_theme"] = self.theme_combo.currentText().lower()
        self.config["ui_font_size"] = self.font_spin.value()
        self.config["window_width"] = self.win_width_spin.value()
        self.config["window_height"] = self.win_height_spin.value()
        self.config["auto_clear_transfers"] = self.auto_clear_checkbox.currentIndex() == 0

        # Telegram
        self.config["api_id"] = self.api_id_edit.text().strip()
        self.config["api_hash"] = self.api_hash_edit.text().strip()
        self.config["phone"] = self.phone_edit.text().strip()

        # Favorites
        self.tab_favorites.save_to_db()
        favs = self.tab_favorites.get_favorite_channels()
        self.config["favorite_channels"] = [
            {"channel_id": ch["channel_id"], "display_name": ch["display_name"]}
            for ch in favs
        ]

        # Tags
        self.tab_tags.save_to_db()

        save_config(self.config)
        self.settings_applied.emit(self.config)
        self.accept()

    def _on_disconnect(self):
        reply = QMessageBox.question(
            self, "Conferma", "Vuoi davvero disconnettere la sessione Telegram?\n"
            "Dovrai reinserire le credenziali al prossimo avvio.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.disconnect_requested.emit()
            self.status_lbl.setText("❌ Disconnesso")

    def _on_reconnect(self):
        self.reconnect_requested.emit()
        self.status_lbl.setText("🔄 Connessione in corso...")
