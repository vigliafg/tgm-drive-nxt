"""
Setup Wizard — Flusso di primo avvio guidato per TGM Drive.

Pagine:
  0. Welcome      — Introduzione e prerequisiti
  1. Credentials  — API ID, API Hash, numero di telefono
  2. Otp          — Codice di verifica Telegram (con retry)
  3. Channel      — Selezione canale cloud
  4. Favorites    — Canali preferiti + cartella download (opzionale)
"""

import sys
from pathlib import Path
from typing import List, Dict, Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QStackedWidget, QWidget, QFormLayout,
    QListWidget, QListWidgetItem, QProgressBar, QGroupBox,
    QFileDialog, QMessageBox, QSpacerItem, QSizePolicy,
    QFrame, QInputDialog
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap, QIcon, QColor, QPalette

from config import save_config, SESSION_FILE
from database import Database
from telegram_client import TelegramClientThread


# ── Stili riutilizzabili ────────────────────────────────────────────────

WIZARD_STYLE = """
    QDialog {
        background-color: #1e1e2e;
        color: #cdd6f4;
    }
    QLabel {
        color: #cdd6f4;
    }
    QLineEdit {
        background-color: #313244;
        color: #cdd6f4;
        border: 1px solid #45475a;
        border-radius: 6px;
        padding: 8px 12px;
        font-size: 14px;
        selection-background-color: #89b4fa;
    }
    QLineEdit:focus {
        border: 1px solid #89b4fa;
    }
    QPushButton {
        color: #cdd6f4;
        border-radius: 6px;
        padding: 8px 18px;
        font-size: 13px;
        font-weight: bold;
    }
    QListWidget {
        background-color: #313244;
        color: #cdd6f4;
        border: 1px solid #45475a;
        border-radius: 6px;
        padding: 4px;
        font-size: 13px;
    }
    QListWidget::item {
        padding: 6px 10px;
        border-radius: 4px;
    }
    QListWidget::item:selected {
        background-color: #89b4fa;
        color: #1e1e2e;
    }
    QListWidget::item:hover {
        background-color: #45475a;
    }
    QGroupBox {
        color: #cdd6f4;
        border: 1px solid #45475a;
        border-radius: 8px;
        margin-top: 14px;
        padding-top: 18px;
        font-weight: bold;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 6px;
    }
    QProgressBar {
        border: 1px solid #45475a;
        border-radius: 4px;
        text-align: center;
        color: #cdd6f4;
        background-color: #313244;
    }
    QProgressBar::chunk {
        background-color: #89b4fa;
        border-radius: 3px;
    }
"""

NAV_BTN_STYLE = """
    QPushButton {
        background-color: #89b4fa;
        color: #1e1e2e;
        border: none;
        border-radius: 6px;
        padding: 10px 24px;
        font-size: 14px;
        font-weight: bold;
    }
    QPushButton:hover {
        background-color: #74c7ec;
    }
    QPushButton:disabled {
        background-color: #45475a;
        color: #6c7086;
    }
"""

SECONDARY_BTN_STYLE = """
    QPushButton {
        background-color: #313244;
        color: #cdd6f4;
        border: 1px solid #45475a;
        border-radius: 6px;
        padding: 10px 24px;
        font-size: 14px;
        font-weight: bold;
    }
    QPushButton:hover {
        background-color: #45475a;
    }
    QPushButton:disabled {
        background-color: #1e1e2e;
        color: #6c7086;
    }
"""

DANGER_BTN_STYLE = """
    QPushButton {
        background-color: #f38ba8;
        color: #1e1e2e;
        border: none;
        border-radius: 6px;
        padding: 10px 24px;
        font-size: 14px;
        font-weight: bold;
    }
    QPushButton:hover {
        background-color: #eba0ac;
    }
"""

STEP_ACTIVE_DOT = """
    QLabel {
        background-color: #89b4fa;
        border-radius: 8px;
        min-width: 16px;
        max-width: 16px;
        min-height: 16px;
        max-height: 16px;
    }
"""

STEP_DONE_DOT = """
    QLabel {
        background-color: #a6e3a1;
        border-radius: 8px;
        min-width: 16px;
        max-width: 16px;
        min-height: 16px;
        max-height: 16px;
    }
"""

STEP_PENDING_DOT = """
    QLabel {
        background-color: #45475a;
        border-radius: 8px;
        min-width: 16px;
        max-width: 16px;
        min-height: 16px;
        max-height: 16px;
    }
"""

STEP_LABEL_ACTIVE = """
    QLabel {
        color: #89b4fa;
        font-size: 12px;
        font-weight: bold;
    }
"""

STEP_LABEL_DONE = """
    QLabel {
        color: #a6e3a1;
        font-size: 12px;
    }
"""

STEP_LABEL_PENDING = """
    QLabel {
        color: #6c7086;
        font-size: 12px;
    }
"""


# ── Pagine del wizard ────────────────────────────────────────────────────


class WelcomePage(QWidget):
    """Pagina 0: Benvenuto e spiegazione."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(16)

        # Icon / logo placeholder
        icon_lbl = QLabel("☁️")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("font-size: 64px;")
        layout.addWidget(icon_lbl)

        title = QLabel("Benvenuto in TGM Drive")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 26px; font-weight: bold; color: #89b4fa;")
        layout.addWidget(title)

        subtitle = QLabel(
            "Trasforma un canale Telegram privato nel tuo cloud personale.\n"
            "Carica, scarica e gestisci file di qualsiasi tipo."
        )
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("font-size: 15px; color: #a6adc8; line-height: 1.5;")
        layout.addWidget(subtitle)

        layout.addSpacing(10)

        # Prerequisites box
        prereq_box = QGroupBox("Cosa ti servirà")
        prereq_box.setStyleSheet(prereq_box.styleSheet() + " QGroupBox { font-size: 14px; }")
        prereq_layout = QVBoxLayout(prereq_box)
        prereq_layout.setSpacing(10)

        items = [
            ("1️⃣", "API ID e API Hash", "da my.telegram.org/apps"),
            ("2️⃣", "Il tuo numero di telefono", "associato all'account Telegram"),
            ("3️⃣", "Un canale Telegram", "di cui sei amministratore"),
        ]
        for num, title_text, desc in items:
            item_layout = QHBoxLayout()
            item_layout.setSpacing(8)
            num_lbl = QLabel(num)
            num_lbl.setStyleSheet("font-size: 20px;")
            item_layout.addWidget(num_lbl)
            text_widget = QLabel(f"<b>{title_text}</b><br><span style='color: #a6adc8;'>{desc}</span>")
            text_widget.setStyleSheet("font-size: 13px;")
            text_widget.setWordWrap(True)
            item_layout.addWidget(text_widget, stretch=1)
            prereq_layout.addLayout(item_layout)

        layout.addWidget(prereq_box)

        layout.addStretch()

        note = QLabel("Ti guideremo passo dopo passo. Bastano 2 minuti.")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note.setStyleSheet("color: #6c7086; font-size: 13px; font-style: italic;")
        layout.addWidget(note)


class CredentialsPage(QWidget):
    """Pagina 1: Inserimento credenziali Telegram."""

    credentials_valid = pyqtSignal()

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.config = config
        self._build_ui()
        self._load_config()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(16)

        title = QLabel("🔑 Credenziali Telegram")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #89b4fa;")
        layout.addWidget(title)

        info = QLabel(
            "Inserisci le credenziali API ottenute da "
            "<a href='https://my.telegram.org/apps' "
            "style='color: #89b4fa;'>my.telegram.org/apps</a>"
        )
        info.setOpenExternalLinks(True)
        info.setWordWrap(True)
        info.setStyleSheet("font-size: 14px; color: #a6adc8;")
        layout.addWidget(info)

        layout.addSpacing(8)

        form = QFormLayout()
        form.setSpacing(12)

        self.api_id_edit = QLineEdit()
        self.api_id_edit.setPlaceholderText("es. 123456")
        self.api_id_edit.textChanged.connect(self._validate)
        form.addRow("API ID:", self.api_id_edit)

        self.api_hash_edit = QLineEdit()
        self.api_hash_edit.setPlaceholderText("es. a1b2c3d4e5f6...")
        self.api_hash_edit.textChanged.connect(self._validate)
        form.addRow("API Hash:", self.api_hash_edit)

        self.phone_edit = QLineEdit()
        self.phone_edit.setPlaceholderText("es. +393331234567")
        self.phone_edit.textChanged.connect(self._validate)
        form.addRow("Telefono:", self.phone_edit)

        layout.addLayout(form)

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("font-size: 13px;")
        layout.addWidget(self.status_lbl)

        layout.addStretch()

        # Help note
        help_note = QLabel(
            "ℹ️ Non hai le credenziali? Vai su my.telegram.org, accedi col tuo numero, "
            "clicca su <b>API development tools</b> e crea una nuova app."
        )
        help_note.setWordWrap(True)
        help_note.setStyleSheet("color: #6c7086; font-size: 12px; padding: 8px;")
        layout.addWidget(help_note)

        self._validate()

    def _load_config(self):
        self.api_id_edit.setText(self.config.get("api_id", ""))
        self.api_hash_edit.setText(self.config.get("api_hash", ""))
        self.phone_edit.setText(self.config.get("phone", ""))

    def _validate(self):
        api_id = self.api_id_edit.text().strip()
        api_hash = self.api_hash_edit.text().strip()
        phone = self.phone_edit.text().strip()

        if not api_id or not api_hash or not phone:
            self.status_lbl.setText("⚠️ Compila tutti i campi")
            self.status_lbl.setStyleSheet("font-size: 13px; color: #f9e2af;")
            return

        try:
            int(api_id)
        except ValueError:
            self.status_lbl.setText("❌ API ID deve essere un numero")
            self.status_lbl.setStyleSheet("font-size: 13px; color: #f38ba8;")
            return

        if not phone.startswith("+"):
            self.status_lbl.setText("⚠️ Il telefono deve iniziare con + (es. +39...)")
            self.status_lbl.setStyleSheet("font-size: 13px; color: #f9e2af;")
            return

        self.status_lbl.setText("✅ Credenziali valide")
        self.status_lbl.setStyleSheet("font-size: 13px; color: #a6e3a1;")
        self.credentials_valid.emit()

    def get_api_id(self) -> str:
        return self.api_id_edit.text().strip()

    def get_api_hash(self) -> str:
        return self.api_hash_edit.text().strip()

    def get_phone(self) -> str:
        return self.phone_edit.text().strip()

    def are_valid(self) -> bool:
        """Verifica rapida, usata dal wizard per abilitare il pulsante Next."""
        api_id = self.api_id_edit.text().strip()
        api_hash = self.api_hash_edit.text().strip()
        phone = self.phone_edit.text().strip()
        if not api_id or not api_hash or not phone:
            return False
        try:
            int(api_id)
        except ValueError:
            return False
        return phone.startswith("+")


class OtpPage(QWidget):
    """Pagina 2: Inserimento codice OTP Telegram (con retry)."""

    otp_submitted = pyqtSignal(str)  # codice OTP

    def __init__(self, phone: str = "", parent=None):
        super().__init__(parent)
        self.phone = phone
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(16)

        title = QLabel("📱 Verifica Telegram")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #89b4fa;")
        layout.addWidget(title)

        self.info_lbl = QLabel("Ti abbiamo inviato un codice di verifica su Telegram.")
        self.info_lbl.setWordWrap(True)
        self.info_lbl.setStyleSheet("font-size: 14px; color: #a6adc8;")
        layout.addWidget(self.info_lbl)

        layout.addSpacing(8)

        form = QFormLayout()
        form.setSpacing(10)

        self.otp_edit = QLineEdit()
        self.otp_edit.setPlaceholderText("es. 12345")
        self.otp_edit.setMaxLength(10)
        self.otp_edit.setStyleSheet(
            "QLineEdit { font-size: 20px; letter-spacing: 8px; text-align: center; padding: 12px; }"
        )
        self.otp_edit.textChanged.connect(self._on_otp_changed)
        form.addRow("Codice OTP:", self.otp_edit)

        layout.addLayout(form)

        self.status_lbl = QLabel("⏳ In attesa del codice...")
        self.status_lbl.setStyleSheet("font-size: 14px; color: #f9e2af;")
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_lbl)

        # Retry area
        retry_layout = QHBoxLayout()
        self.retry_btn = QPushButton("🔄 Richiedi nuovo codice")
        self.retry_btn.setStyleSheet(SECONDARY_BTN_STYLE)
        self.retry_btn.setEnabled(False)
        self.retry_btn.clicked.connect(self._on_retry)
        retry_layout.addStretch()
        retry_layout.addWidget(self.retry_btn)
        retry_layout.addStretch()
        layout.addLayout(retry_layout)

        layout.addStretch()

        self._countdown_seconds = 0
        self._countdown_timer = QTimer(self)
        self._countdown_timer.timeout.connect(self._tick_countdown)

    def set_phone(self, phone: str):
        self.phone = phone
        self.info_lbl.setText(
            f"Ti abbiamo inviato un codice di verifica su Telegram al numero {phone}."
        )

    def reset_state(self):
        """Resetta lo stato per un nuovo tentativo."""
        self.otp_edit.clear()
        self.otp_edit.setFocus()
        self.status_lbl.setText("⏳ In attesa del codice...")
        self.status_lbl.setStyleSheet("font-size: 14px; color: #f9e2af;")
        self.retry_btn.setEnabled(False)
        self._countdown_seconds = 30
        self._countdown_timer.start(1000)
        self.retry_btn.setText("🔄 Richiedi nuovo codice (30s)")

    def set_error(self, message: str):
        """Mostra un errore (es. OTP sbagliato)."""
        short_msg = message[:120] if message else "Codice non valido"
        self.status_lbl.setText(f"❌ {short_msg}")
        self.status_lbl.setStyleSheet("font-size: 14px; color: #f38ba8;")
        self.otp_edit.clear()
        self.otp_edit.setFocus()

    def set_success(self):
        """Mostra stato di successo."""
        self.status_lbl.setText("✅ Verifica completata!")
        self.status_lbl.setStyleSheet("font-size: 14px; color: #a6e3a1;")

    def set_connecting(self):
        self.status_lbl.setText("⏳ Connessione in corso...")
        self.status_lbl.setStyleSheet("font-size: 14px; color: #f9e2af;")

    def _on_otp_changed(self, text: str):
        if text.strip():
            self.otp_submitted.emit(text.strip())

    def _on_retry(self):
        self.otp_submitted.emit("__RETRY__")

    def _tick_countdown(self):
        self._countdown_seconds -= 1
        if self._countdown_seconds <= 0:
            self._countdown_timer.stop()
            self.retry_btn.setEnabled(True)
            self.retry_btn.setText("🔄 Richiedi nuovo codice")
        else:
            self.retry_btn.setText(f"🔄 Richiedi nuovo codice ({self._countdown_seconds}s)")

    def get_otp(self) -> str:
        return self.otp_edit.text().strip()


class ChannelPage(QWidget):
    """Pagina 3: Selezione canale Telegram."""

    channel_selected = pyqtSignal()

    def __init__(self, tg_client: Optional[TelegramClientThread], db: Database, parent=None):
        super().__init__(parent)
        self.tg_client = tg_client
        self.db = db
        self.selected_channel_id: Optional[int] = None
        self.selected_channel_name: str = ""
        self._all_channels: List[Dict] = []
        self._signals_connected = False
        self._build_ui()
        if self.tg_client is not None:
            self._connect_signals()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(12)

        title = QLabel("📢 Scegli il Canale Cloud")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #89b4fa;")
        layout.addWidget(title)

        info = QLabel(
            "Seleziona il canale Telegram che userai come spazio cloud. "
            "Devi essere <b>amministratore</b> del canale per poter caricare file."
        )
        info.setWordWrap(True)
        info.setStyleSheet("font-size: 14px; color: #a6adc8;")
        layout.addWidget(info)

        # Search bar
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 Cerca canale per nome...")
        self.search_edit.textChanged.connect(self._on_search)
        layout.addWidget(self.search_edit)

        # Channel list
        self.list_widget = QListWidget()
        self.list_widget.setMinimumHeight(180)
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        self.list_widget.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self.list_widget)

        # Progress bar (nascosta finché non carica)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        self.progress.setMaximumHeight(6)
        layout.addWidget(self.progress)

        # Selected channel info
        self.selected_lbl = QLabel("")
        self.selected_lbl.setStyleSheet("font-size: 13px; color: #a6adc8;")
        layout.addWidget(self.selected_lbl)

        # Manual ID fallback
        manual_box = QGroupBox("Oppure inserisci l'ID manualmente")
        manual_layout = QHBoxLayout(manual_box)
        manual_layout.setSpacing(8)
        self.manual_edit = QLineEdit()
        self.manual_edit.setPlaceholderText("es. -1001234567890")
        self.manual_btn = QPushButton("Usa ID")
        self.manual_btn.setStyleSheet(SECONDARY_BTN_STYLE)
        self.manual_btn.clicked.connect(self._on_manual)
        manual_layout.addWidget(self.manual_edit, stretch=1)
        manual_layout.addWidget(self.manual_btn)
        layout.addWidget(manual_box)

        # Create channel button
        create_layout = QHBoxLayout()
        self.create_btn = QPushButton("➕ Crea nuovo canale")
        self.create_btn.setStyleSheet(NAV_BTN_STYLE)
        self.create_btn.setToolTip("Crea un nuovo canale Telegram privato e selezionalo automaticamente")
        self.create_btn.clicked.connect(self._on_create_channel)
        create_layout.addStretch()
        create_layout.addWidget(self.create_btn)
        create_layout.addStretch()
        layout.addLayout(create_layout)

        # Status
        self.status_lbl = QLabel("Caricamento canali in corso...")
        self.status_lbl.setStyleSheet("font-size: 13px; color: #f9e2af;")
        layout.addWidget(self.status_lbl)

        layout.addStretch()

    def set_tg_client(self, tg_client: TelegramClientThread):
        """Imposta o aggiorna il client Telegram (usato dal wizard dopo la connessione)."""
        if self._signals_connected and self.tg_client:
            for sig_name in ("channels_ready", "channel_created", "error_occurred"):
                try:
                    getattr(self.tg_client, sig_name).disconnect()
                except TypeError:
                    pass
            self._signals_connected = False
        self.tg_client = tg_client
        if tg_client is not None:
            self._connect_signals()

    def _connect_signals(self):
        self.tg_client.channels_ready.connect(self._on_channels_ready)
        self.tg_client.channel_created.connect(self._on_channel_created)
        self.tg_client.error_occurred.connect(self._on_error)
        try:
            self.manual_edit.returnPressed.disconnect(self._on_manual)
        except TypeError:
            pass
        self.manual_edit.returnPressed.connect(self._on_manual)
        self._signals_connected = True

    def load_channels(self):
        """Avvia il caricamento dei canali da Telegram."""
        self.status_lbl.setText("Caricamento canali in corso...")
        self.status_lbl.setStyleSheet("font-size: 13px; color: #f9e2af;")
        self.progress.setVisible(True)
        self.list_widget.clear()
        item = QListWidgetItem("Caricamento...")
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        self.list_widget.addItem(item)
        self.tg_client.list_channels()

    def _on_channels_ready(self, channels: List[Dict]):
        self.progress.setVisible(False)
        self._all_channels = sorted(channels, key=lambda x: x.get('title', '').lower())
        if not self._all_channels:
            self.list_widget.clear()
            item = QListWidgetItem("Nessun canale trovato. Inserisci l'ID manualmente qui sotto.")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list_widget.addItem(item)
            self.status_lbl.setText("⚠️ Nessun canale trovato — sei amministratore di qualche canale?")
            self.status_lbl.setStyleSheet("font-size: 13px; color: #f9e2af;")
            return
        self.status_lbl.setText(
            f"✅ {len(self._all_channels)} canali trovati — selezionane uno"
        )
        self.status_lbl.setStyleSheet("font-size: 13px; color: #a6e3a1;")
        self._filter_channels("")

    def _on_error(self, msg: str):
        self.progress.setVisible(False)
        self.create_btn.setEnabled(True)
        self.status_lbl.setText(f"❌ Errore: {msg[:100]}")
        self.status_lbl.setStyleSheet("font-size: 13px; color: #f38ba8;")

    def _filter_channels(self, query: str):
        self.list_widget.clear()
        q = query.lower()
        visible = []
        for ch in self._all_channels:
            if q in ch.get('title', '').lower() or q in (ch.get('username', '') or '').lower():
                visible.append(ch)
        if not visible:
            item = QListWidgetItem("Nessun canale corrispondente alla ricerca")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list_widget.addItem(item)
            return
        for ch in visible:
            display = f"{ch['title']}"
            if ch.get('username'):
                display += f"  (@{ch['username']})"
            display += f"  —  ID: {ch['id']}"
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, ch['id'])
            self.list_widget.addItem(item)

    def _on_search(self, text: str):
        if not self._all_channels:
            return
        self._filter_channels(text)

    def _on_selection_changed(self):
        item = self.list_widget.currentItem()
        if item and item.flags() & Qt.ItemFlag.ItemIsEnabled:
            ch_id = item.data(Qt.ItemDataRole.UserRole)
            ch_name = item.text().split("  —  ID:")[0].strip()
            self.selected_channel_id = ch_id
            self.selected_channel_name = ch_name
            self.selected_lbl.setText(f"📁 Selezionato: {ch_name} (ID: {ch_id})")
            self.selected_lbl.setStyleSheet("font-size: 13px; color: #89b4fa; font-weight: bold;")
            self.channel_selected.emit()

    def _on_double_click(self, item):
        if item and item.flags() & Qt.ItemFlag.ItemIsEnabled:
            self.channel_selected.emit()

    def _on_manual(self):
        text = self.manual_edit.text().strip()
        if not text:
            return
        try:
            ch_id = int(text)
            self.selected_channel_id = ch_id
            self.selected_channel_name = f"Canale {text}"
            self.selected_lbl.setText(f"📁 Selezionato: Canale {text} (ID: {ch_id})")
            self.selected_lbl.setStyleSheet("font-size: 13px; color: #89b4fa; font-weight: bold;")
            self.channel_selected.emit()
        except ValueError:
            QMessageBox.warning(self, "Errore", "ID canale non valido. Usa un numero (es. -1001234567890)")

    def _on_create_channel(self):
        """Chiede nome e descrizione, poi crea un nuovo canale Telegram privato."""
        name, ok = QInputDialog.getText(
            self, "Nuovo canale", "Nome del canale:"
        )
        if not ok or not name.strip():
            return
        title = name.strip()
        about, ok2 = QInputDialog.getText(
            self, "Nuovo canale", "Descrizione (opzionale):"
        )
        if not ok2:
            return
        self.status_lbl.setText(f"Creazione canale '{title}' in corso...")
        self.status_lbl.setStyleSheet("font-size: 13px; color: #f9e2af;")
        self.create_btn.setEnabled(False)
        self.tg_client.create_channel(title, about.strip() if about else "")

    def _on_channel_created(self, channel_info: dict):
        """Callback alla creazione riuscita del canale: ricarica la lista e auto-seleziona."""
        self.create_btn.setEnabled(True)
        ch_id = channel_info["id"]
        ch_name = channel_info["title"]
        self.selected_channel_id = ch_id
        self.selected_channel_name = ch_name
        self.selected_lbl.setText(f"📁 Selezionato: {ch_name} (ID: {ch_id})")
        self.selected_lbl.setStyleSheet("font-size: 13px; color: #89b4fa; font-weight: bold;")
        self.status_lbl.setText(f"✅ Canale '{ch_name}' creato con successo!")
        self.status_lbl.setStyleSheet("font-size: 13px; color: #a6e3a1;")
        # Ricarica la lista (la selezione resta valida perché già impostata sopra)
        self.load_channels()
        self.channel_selected.emit()

    def is_channel_selected(self) -> bool:
        return self.selected_channel_id is not None


class FavoritesPage(QWidget):
    """Pagina 4: Configurazione rapida canali preferiti e cartella download."""

    def __init__(self, db: Database, tg_client: Optional[TelegramClientThread],
                 current_channel_id: int = 0, current_channel_name: str = "",
                 download_dir: str = "", parent=None):
        super().__init__(parent)
        self.db = db
        self.tg_client = tg_client
        self.current_channel_id = current_channel_id
        self.current_channel_name = current_channel_name
        self.download_dir = download_dir or str(Path.home() / "TGM_Drive_Downloads")
        self._favorites: List[Dict] = []
        self._telegram_channels: List[Dict] = []
        self._signals_connected = False
        self._build_ui()
        if self.tg_client is not None:
            self._connect_signals()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(12)

        title = QLabel("⭐ Configurazione Rapida")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #89b4fa;")
        layout.addWidget(title)

        subtitle = QLabel(
            "Aggiungi i canali più usati ai <b>preferiti</b> per accedervi "
            "con un clic dalla barra in alto. Puoi sempre modificarli dopo dalle Impostazioni."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("font-size: 14px; color: #a6adc8;")
        layout.addWidget(subtitle)

        # Favorites quick-add section
        fav_layout = QHBoxLayout()
        fav_layout.setSpacing(12)

        # Left: channel selector
        left_box = QGroupBox("Canali disponibili")
        left_inner = QVBoxLayout(left_box)
        self.channel_list = QListWidget()
        left_inner.addWidget(self.channel_list)

        load_btn = QPushButton("🔄 Carica canali")
        load_btn.setStyleSheet(SECONDARY_BTN_STYLE)
        load_btn.clicked.connect(self._load_telegram_channels)
        left_inner.addWidget(load_btn)

        fav_layout.addWidget(left_box, stretch=1)

        # Center: add button
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.add_btn = QPushButton("➕\nAggiungi\nai Preferiti")
        self.add_btn.setStyleSheet(NAV_BTN_STYLE)
        self.add_btn.setMinimumWidth(100)
        self.add_btn.setMinimumHeight(70)
        self.add_btn.clicked.connect(self._on_add)
        center_layout.addWidget(self.add_btn)
        fav_layout.addWidget(center_widget)

        # Right: favorites list
        right_box = QGroupBox("⭐ I tuoi preferiti")
        right_inner = QVBoxLayout(right_box)
        self.fav_list = QListWidget()
        self.fav_list.itemDoubleClicked.connect(self._on_rename)
        right_inner.addWidget(self.fav_list)

        fav_btn_layout = QHBoxLayout()
        self.btn_up = QPushButton("⬆")
        self.btn_up.setStyleSheet(SECONDARY_BTN_STYLE)
        self.btn_up.clicked.connect(self._on_move_up)
        self.btn_down = QPushButton("⬇")
        self.btn_down.setStyleSheet(SECONDARY_BTN_STYLE)
        self.btn_down.clicked.connect(self._on_move_down)
        self.btn_rename = QPushButton("✏️")
        self.btn_rename.setStyleSheet(SECONDARY_BTN_STYLE)
        self.btn_rename.clicked.connect(self._on_rename)
        self.btn_remove = QPushButton("🗑")
        self.btn_remove.setStyleSheet(DANGER_BTN_STYLE)
        self.btn_remove.clicked.connect(self._on_remove)
        fav_btn_layout.addWidget(self.btn_up)
        fav_btn_layout.addWidget(self.btn_down)
        fav_btn_layout.addWidget(self.btn_rename)
        fav_btn_layout.addWidget(self.btn_remove)
        right_inner.addLayout(fav_btn_layout)

        fav_layout.addWidget(right_box, stretch=1)

        layout.addLayout(fav_layout)

        # Auto-add current channel
        auto_layout = QHBoxLayout()
        self.auto_add_lbl = QLabel(
            f"💡 Il canale <b>{self.current_channel_name}</b> è già stato aggiunto."
            if self.current_channel_id in {f['channel_id'] for f in self._favorites}
            else f"💡 Il canale <b>{self.current_channel_name}</b> sarà aggiunto automaticamente."
        )
        self.auto_add_lbl.setWordWrap(True)
        self.auto_add_lbl.setStyleSheet("font-size: 13px; color: #a6adc8;")
        auto_layout.addWidget(self.auto_add_lbl)
        layout.addLayout(auto_layout)

        # Download folder
        dl_box = QGroupBox("📂 Cartella Download")
        dl_layout = QHBoxLayout(dl_box)
        dl_layout.setSpacing(8)
        self.dl_path_edit = QLineEdit(self.download_dir)
        self.dl_path_edit.setReadOnly(True)
        self.dl_path_edit.setStyleSheet(
            "QLineEdit { background-color: #313244; color: #a6adc8; }"
        )
        dl_layout.addWidget(self.dl_path_edit, stretch=1)
        dl_browse_btn = QPushButton("📂 Sfoglia")
        dl_browse_btn.setStyleSheet(SECONDARY_BTN_STYLE)
        dl_browse_btn.clicked.connect(self._on_browse_download)
        dl_layout.addWidget(dl_browse_btn)
        layout.addWidget(dl_box)

        layout.addStretch()

        # Skip note
        skip_note = QLabel("Puoi saltare questo passo e configurare tutto dopo dalle Impostazioni.")
        skip_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        skip_note.setStyleSheet("color: #6c7086; font-size: 12px; font-style: italic;")
        layout.addWidget(skip_note)

    def set_tg_client(self, tg_client: TelegramClientThread):
        """Imposta o aggiorna il client Telegram (usato dal wizard dopo la connessione)."""
        if self._signals_connected and self.tg_client:
            for sig_name in ("channels_ready", "error_occurred"):
                try:
                    getattr(self.tg_client, sig_name).disconnect()
                except TypeError:
                    pass
            self._signals_connected = False
        self.tg_client = tg_client
        if tg_client is not None:
            self._connect_signals()

    def _connect_signals(self):
        self.tg_client.channels_ready.connect(self._on_telegram_channels_ready)
        self.tg_client.error_occurred.connect(self._on_error)
        self._signals_connected = True

    # ── Initialization ──────────────────────────────────────────────

    def init_defaults(self):
        """Aggiunge automaticamente il canale corrente ai preferiti."""
        if self.current_channel_id and self.current_channel_id not in {
            f['channel_id'] for f in self._favorites
        }:
            self._favorites.append({
                'channel_id': self.current_channel_id,
                'channel_name': self.current_channel_name,
                'display_name': self.current_channel_name,
                'sort_order': len(self._favorites),
            })
            self._refresh_fav_list()
        self._load_telegram_channels()

    # ── Telegram channels ───────────────────────────────────────────

    def _load_telegram_channels(self):
        self.channel_list.clear()
        item = QListWidgetItem("Caricamento...")
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        self.channel_list.addItem(item)
        self.tg_client.list_channels()

    def _on_telegram_channels_ready(self, channels: List[Dict]):
        self._telegram_channels = sorted(channels, key=lambda x: x.get('title', '').lower())
        self.channel_list.clear()
        fav_ids = {f['channel_id'] for f in self._favorites}
        for ch in self._telegram_channels:
            if ch['id'] in fav_ids:
                continue
            display = ch['title']
            if ch.get('username'):
                display += f"  (@{ch['username']})"
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, ch)
            self.channel_list.addItem(item)
        if self.channel_list.count() == 0:
            item = QListWidgetItem("Nessun altro canale disponibile")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.channel_list.addItem(item)

    def _on_error(self, msg: str):
        self.channel_list.clear()
        item = QListWidgetItem(f"Errore: {msg[:80]}")
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        self.channel_list.addItem(item)

    # ── Favorites management ────────────────────────────────────────

    def _on_add(self):
        item = self.channel_list.currentItem()
        if not item or not item.flags() & Qt.ItemFlag.ItemIsEnabled:
            return
        ch = item.data(Qt.ItemDataRole.UserRole)
        if not ch or not isinstance(ch, dict):
            return
        new_fav = {
            'channel_id': ch['id'],
            'channel_name': ch['title'],
            'display_name': ch['title'],
            'sort_order': len(self._favorites),
        }
        self._favorites.append(new_fav)
        self._refresh_fav_list()
        self._on_telegram_channels_ready(self._telegram_channels)

    def _on_remove(self):
        idx = self.fav_list.currentRow()
        if idx < 0:
            return
        self._favorites.pop(idx)
        for i, f in enumerate(self._favorites):
            f['sort_order'] = i
        self._refresh_fav_list()
        self._on_telegram_channels_ready(self._telegram_channels)

    def _on_move_up(self):
        idx = self.fav_list.currentRow()
        if idx <= 0:
            return
        self._favorites[idx], self._favorites[idx - 1] = (
            self._favorites[idx - 1], self._favorites[idx]
        )
        for i, f in enumerate(self._favorites):
            f['sort_order'] = i
        self._refresh_fav_list()
        self.fav_list.setCurrentRow(idx - 1)

    def _on_move_down(self):
        idx = self.fav_list.currentRow()
        if idx < 0 or idx >= len(self._favorites) - 1:
            return
        self._favorites[idx], self._favorites[idx + 1] = (
            self._favorites[idx + 1], self._favorites[idx]
        )
        for i, f in enumerate(self._favorites):
            f['sort_order'] = i
        self._refresh_fav_list()
        self.fav_list.setCurrentRow(idx + 1)

    def _on_rename(self):
        idx = self.fav_list.currentRow()
        if idx < 0:
            return
        ch = self._favorites[idx]
        new_name, ok = QInputDialog.getText(
            self, "Rinomina", "Nome visualizzato:", text=ch['display_name']
        )
        if ok and new_name.strip():
            ch['display_name'] = new_name.strip()
            self._refresh_fav_list()

    def _refresh_fav_list(self):
        self.fav_list.clear()
        for f in self._favorites:
            item = QListWidgetItem(
                f"{f['display_name']}  (ID: {f['channel_id']})"
            )
            item.setData(Qt.ItemDataRole.UserRole, f)
            self.fav_list.addItem(item)

    # ── Download folder ─────────────────────────────────────────────

    def _on_browse_download(self):
        path = QFileDialog.getExistingDirectory(
            self, "Seleziona cartella download", self.download_dir
        )
        if path:
            self.download_dir = path
            self.dl_path_edit.setText(path)

    # ── Public API ──────────────────────────────────────────────────

    def get_favorites(self) -> List[Dict]:
        return self._favorites

    def get_download_dir(self) -> str:
        return self.download_dir

    def save(self):
        """Salva preferiti e cartella download nel DB."""
        self.db.set_favorite_channels(self._favorites)
        for f in self._favorites:
            self.db.insert_or_update_channel(f['channel_id'], f['channel_name'])
        Path(self.download_dir).mkdir(parents=True, exist_ok=True)


# ── Wizard principale ─────────────────────────────────────────────────────

class SetupWizard(QDialog):
    """Wizard di primo avvio con navigazione guidata passo-passo."""

    PAGE_WELCOME = 0
    PAGE_CREDENTIALS = 1
    PAGE_OTP = 2
    PAGE_CHANNEL = 3
    PAGE_FAVORITES = 4

    wizard_finished = pyqtSignal(dict, object)  # config, tg_client

    def __init__(self, config: dict, db: Database, parent=None):
        super().__init__(parent)
        self.config = config
        self.db = db
        self.tg_client: Optional[TelegramClientThread] = None
        self._current_page = 0
        self._visited_pages: set = set()  # pagine già completate
        self._otp_retry_count = 0
        self._max_otp_retries = 3

        self.setWindowTitle("Configurazione TGM Drive")
        self.setMinimumSize(680, 560)
        self.setStyleSheet(WIZARD_STYLE)

        self._build_ui()
        self._create_pages()
        self._go_to_page(self.PAGE_WELCOME)

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Step indicator
        steps_widget = QWidget()
        steps_widget.setStyleSheet("background-color: #181825; border-bottom: 1px solid #313244;")
        steps_layout = QHBoxLayout(steps_widget)
        steps_layout.setContentsMargins(24, 14, 24, 14)
        steps_layout.setSpacing(10)
        steps_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.step_dots: List[QLabel] = []
        self.step_labels: List[QLabel] = []
        step_names = ["Benvenuto", "Credenziali", "Verifica", "Canale", "Preferiti"]

        for i, name in enumerate(step_names):
            if i > 0:
                sep = QLabel("─")
                sep.setStyleSheet("color: #45475a; font-size: 14px;")
                sep.setFixedWidth(24)
                sep.setAlignment(Qt.AlignmentFlag.AlignCenter)
                steps_layout.addWidget(sep)

            dot = QLabel("●")
            dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dot.setFixedSize(20, 20)
            self.step_dots.append(dot)

            lbl = QLabel(name)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

            vbox = QVBoxLayout()
            vbox.setSpacing(4)
            vbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vbox.addWidget(dot, alignment=Qt.AlignmentFlag.AlignCenter)
            vbox.addWidget(lbl, alignment=Qt.AlignmentFlag.AlignCenter)

            wrapper = QWidget()
            wrapper.setLayout(vbox)
            steps_layout.addWidget(wrapper)
            self.step_labels.append(lbl)

        main_layout.addWidget(steps_widget)

        # Stacked pages
        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack, stretch=1)

        # Navigation bar
        nav_widget = QWidget()
        nav_widget.setStyleSheet("background-color: #181825; border-top: 1px solid #313244;")
        nav_layout = QHBoxLayout(nav_widget)
        nav_layout.setContentsMargins(24, 12, 24, 12)
        nav_layout.setSpacing(12)

        self.cancel_btn = QPushButton("❌ Annulla")
        self.cancel_btn.setStyleSheet(SECONDARY_BTN_STYLE)
        self.cancel_btn.clicked.connect(self._on_cancel)
        nav_layout.addWidget(self.cancel_btn)

        nav_layout.addStretch()

        self.back_btn = QPushButton("← Indietro")
        self.back_btn.setStyleSheet(SECONDARY_BTN_STYLE)
        self.back_btn.clicked.connect(self._go_back)
        nav_layout.addWidget(self.back_btn)

        self.next_btn = QPushButton("Avanti →")
        self.next_btn.setStyleSheet(NAV_BTN_STYLE)
        self.next_btn.clicked.connect(self._go_next)
        self.next_btn.setDefault(True)
        nav_layout.addWidget(self.next_btn)

        main_layout.addWidget(nav_widget)

    def _create_pages(self):
        # Page 0: Welcome
        self.welcome_page = WelcomePage()
        self.stack.addWidget(self.welcome_page)

        # Page 1: Credentials
        self.credentials_page = CredentialsPage(self.config)
        self.stack.addWidget(self.credentials_page)

        # Page 2: OTP (tg_client non ancora creato — placeholder)
        self.otp_page = OtpPage()
        self.stack.addWidget(self.otp_page)

        # Page 3: Channel (tg_client non ancora creato — placeholder)
        self.channel_page = ChannelPage(None, self.db)  # verrà aggiornato
        self.stack.addWidget(self.channel_page)

        # Page 4: Favorites (tg_client già creato a questo punto)
        self.favorites_page = FavoritesPage(
            self.db, None,  # tg_client aggiornato dopo connessione
            download_dir=self.config.get("download_dir", "")
        )
        self.stack.addWidget(self.favorites_page)

    # ── Navigazione ──────────────────────────────────────────────────

    def _go_to_page(self, page_idx: int):
        """Naviga alla pagina specificata e aggiorna UI."""
        self._current_page = page_idx
        self.stack.setCurrentIndex(page_idx)
        self._update_step_indicator()
        self._update_nav_buttons()

        # Azioni specifiche per pagina
        if page_idx == self.PAGE_WELCOME:
            self.next_btn.setText("Inizia →")
        elif page_idx == self.PAGE_CREDENTIALS:
            self.next_btn.setText("Connetti →")
            self.credentials_page._validate()
        elif page_idx == self.PAGE_OTP:
            self.next_btn.setText("Verifica →")
        elif page_idx == self.PAGE_CHANNEL:
            self.next_btn.setText("Avanti →")
        elif page_idx == self.PAGE_FAVORITES:
            self.next_btn.setText("✨ Completa!")

    def _go_next(self):
        """Azione del pulsante Avanti/Connetti/Verifica/Completa."""
        page = self._current_page

        if page == self.PAGE_WELCOME:
            self._visited_pages.add(self.PAGE_WELCOME)
            self._go_to_page(self.PAGE_CREDENTIALS)

        elif page == self.PAGE_CREDENTIALS:
            if not self.credentials_page.are_valid():
                return
            self._visited_pages.add(self.PAGE_CREDENTIALS)
            self._start_telegram_connection()

        elif page == self.PAGE_OTP:
            otp = self.otp_page.get_otp()
            if not otp:
                return
            self._submit_otp(otp)

        elif page == self.PAGE_CHANNEL:
            if not self.channel_page.is_channel_selected():
                QMessageBox.information(self, "Seleziona canale", "Scegli un canale dalla lista o inserisci un ID manualmente.")
                return
            self._visited_pages.add(self.PAGE_CHANNEL)
            self._on_channel_confirmed()

        elif page == self.PAGE_FAVORITES:
            self._finish_wizard()

    def _go_back(self):
        if self._current_page == self.PAGE_CREDENTIALS:
            self._go_to_page(self.PAGE_WELCOME)
        elif self._current_page == self.PAGE_CHANNEL:
            # Non si può tornare alla pagina OTP dopo la connessione
            self._go_to_page(self.PAGE_CREDENTIALS)
        elif self._current_page == self.PAGE_FAVORITES:
            self._go_to_page(self.PAGE_CHANNEL)

    def _on_cancel(self):
        reply = QMessageBox.question(
            self, "Annulla configurazione",
            "Sei sicuro di voler annullare? Potrai riprendere la configurazione al prossimo avvio.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            if self.tg_client:
                self.tg_client.stop()
            self.reject()

    def _update_nav_buttons(self):
        page = self._current_page
        self.back_btn.setVisible(page not in (self.PAGE_WELCOME, self.PAGE_OTP))
        self.back_btn.setEnabled(page not in (self.PAGE_WELCOME, self.PAGE_OTP))
        self.next_btn.setEnabled(True)

        if page == self.PAGE_OTP:
            self.next_btn.setEnabled(bool(self.otp_page.get_otp()))

    def _update_step_indicator(self):
        for i in range(len(self.step_dots)):
            if i < self._current_page or i in self._visited_pages:
                self.step_dots[i].setStyleSheet(STEP_DONE_DOT)
                self.step_labels[i].setStyleSheet(STEP_LABEL_DONE)
            elif i == self._current_page:
                self.step_dots[i].setStyleSheet(STEP_ACTIVE_DOT)
                self.step_labels[i].setStyleSheet(STEP_LABEL_ACTIVE)
            else:
                self.step_dots[i].setStyleSheet(STEP_PENDING_DOT)
                self.step_labels[i].setStyleSheet(STEP_LABEL_PENDING)

    # ── Connessione Telegram ─────────────────────────────────────────

    def _start_telegram_connection(self):
        """Crea il TelegramClientThread e avvia la connessione."""
        api_id = int(self.credentials_page.get_api_id())
        api_hash = self.credentials_page.get_api_hash()
        phone = self.credentials_page.get_phone()

        # Salva immediatamente le credenziali
        self.config["api_id"] = str(api_id)
        self.config["api_hash"] = api_hash
        self.config["phone"] = phone
        save_config(self.config)

        # Ferma e disconnetti il vecchio client se esiste
        if self.tg_client is not None:
            self._disconnect_wizard_signals()
            self.tg_client.stop()
            self.tg_client = None

        # Crea il client Telegram
        self.tg_client = TelegramClientThread(api_id, api_hash, str(SESSION_FILE))
        self.tg_client.set_phone(phone)

        # Connetti i segnali
        self.tg_client.otp_required.connect(self._on_otp_required)
        self.tg_client.connected.connect(self._on_connected)
        self.tg_client.error_occurred.connect(self._on_connection_error)

        # Connetti il segnale otp_submitted per riabilitare il pulsante Next dopo errori
        self.otp_page.otp_submitted.connect(self._on_otp_text_changed)

        # Resetta contatore retry per questo tentativo di connessione
        self._otp_retry_count = 0

        # Vai alla pagina OTP (con stato di attesa)
        self._go_to_page(self.PAGE_OTP)
        self.otp_page.set_phone(phone)
        self.otp_page.reset_state()
        self.next_btn.setEnabled(False)

        # Avvia il thread
        self.tg_client.start()

    def _on_otp_text_changed(self, text: str):
        """Richiamato quando l'utente digita nell'OTP edit.
        Riabilita il pulsante Next dopo un errore OTP."""
        if text.strip() and self._current_page == self.PAGE_OTP:
            self.next_btn.setEnabled(True)

    def _disconnect_wizard_signals(self):
        """Scollega tutti i segnali del wizard dal tg_client."""
        if self.tg_client is None:
            return
        for signal_name in ("otp_required", "connected", "error_occurred"):
            try:
                getattr(self.tg_client, signal_name).disconnect()
            except TypeError:
                pass

    def _on_otp_required(self, msg: str):
        """Telegram richiede il codice OTP."""
        self.otp_page.info_lbl.setText(msg)
        self.otp_page.set_connecting()

    def _submit_otp(self, otp_code: str):
        """Invia il codice OTP al client Telegram."""
        if not self.tg_client:
            return
        self.otp_page.set_connecting()
        self.next_btn.setEnabled(False)
        self.tg_client.set_otp(otp_code)

    def _on_connected(self, success: bool, msg: str):
        if not success:
            self._on_connection_error(msg)
            return

        self._visited_pages.add(self.PAGE_OTP)
        self.otp_page.set_success()

        # Aggiorna channel page con il client connesso
        self.channel_page.set_tg_client(self.tg_client)

        self.config["session_ok"] = True
        save_config(self.config)

        QTimer.singleShot(300, lambda: self._on_auth_success())

    def _on_auth_success(self):
        """Dopo autenticazione riuscita, carica i canali."""
        self._go_to_page(self.PAGE_CHANNEL)
        self.channel_page.load_channels()

    def _on_connection_error(self, msg: str):
        """Gestione errore di connessione / OTP errato."""
        if self._current_page == self.PAGE_OTP:
            self._otp_retry_count += 1
            if self._otp_retry_count >= self._max_otp_retries:
                QMessageBox.critical(
                    self, "Errore di verifica",
                    f"Verifica fallita dopo {self._max_otp_retries} tentativi.\n\n"
                    f"Errore: {msg}\n\n"
                    "Torna indietro per reinserire le credenziali o riprova più tardi."
                )
                if self.tg_client:
                    self._disconnect_wizard_signals()
                    self.tg_client.stop()
                self._go_to_page(self.PAGE_CREDENTIALS)
                return

            self.otp_page.set_error(msg)
            # next_btn verrà riabilitato da _on_otp_text_changed quando l'utente digita
        else:
            # Errore generico durante la connessione iniziale
            QMessageBox.critical(
                self, "Errore di connessione",
                f"Impossibile connettersi a Telegram:\n\n{msg}\n\n"
                "Verifica le credenziali e riprova."
            )
            if self.tg_client:
                self._disconnect_wizard_signals()
                self.tg_client.stop()
            self._go_to_page(self.PAGE_CREDENTIALS)

    # ── Canale ───────────────────────────────────────────────────────

    def _on_channel_confirmed(self):
        """Dopo selezione canale, configura i preferiti e procedi."""
        ch_id = self.channel_page.selected_channel_id
        ch_name = self.channel_page.selected_channel_name

        self.config["channel_id"] = str(ch_id)
        self.config["channel_name"] = ch_name
        save_config(self.config)

        # Salva canale nel DB
        self.db.insert_or_update_channel(ch_id, ch_name)

        # Configura la pagina preferiti
        self.favorites_page.set_tg_client(self.tg_client)
        self.favorites_page.current_channel_id = ch_id
        self.favorites_page.current_channel_name = ch_name
        self.favorites_page.init_defaults()

        self._go_to_page(self.PAGE_FAVORITES)

    # ── Completamento ───────────────────────────────────────────────

    def _finish_wizard(self):
        """Salva tutto, disconnette i segnali del wizard, e completa."""
        # Salva preferiti
        self.favorites_page.save()

        # Aggiorna config con download dir
        dl_dir = self.favorites_page.get_download_dir()
        self.config["download_dir"] = dl_dir

        # Aggiorna config con i preferiti
        favs = self.favorites_page.get_favorites()
        self.config["favorite_channels"] = [
            {"channel_id": f["channel_id"], "display_name": f["display_name"]}
            for f in favs
        ]

        save_config(self.config)

        # Scollega i segnali del wizard dal tg_client per evitare
        # che errori di trasferimento futuri attivino gli handler del wizard
        self._disconnect_wizard_signals()

        # Emetti segnale con config e client
        client = self.tg_client
        self.tg_client = None  # Il client ora appartiene a main.py
        self.wizard_finished.emit(self.config, client)
        self.accept()

    def closeEvent(self, event):
        if self.tg_client and not self.tg_client.is_connected():
            self.tg_client.stop()
        event.accept()
