from typing import List, Dict, Callable

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QLabel, QScrollArea, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal


class FavoriteChannelsBar(QWidget):
    """Barra orizzontale di canali preferiti con selezione rapida a un click."""

    channel_selected = pyqtSignal(int, str)  # channel_id, channel_name
    add_to_favorites_requested = pyqtSignal(int, str)  # channel_id, channel_name

    def __init__(self, parent=None):
        super().__init__(parent)
        self._channels: List[Dict] = []
        self._current_channel_id: int = 0
        self._buttons: Dict[int, QPushButton] = {}
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.title_lbl = QLabel("⭐ Preferiti:")
        self.title_lbl.setStyleSheet("font-weight: bold; color: #FFD700;")
        layout.addWidget(self.title_lbl)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setMaximumHeight(42)

        self.container = QWidget()
        self.container_layout = QHBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(6)
        self.container_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll, stretch=1)

        self.add_btn = QPushButton("➕")
        self.add_btn.setToolTip("Aggiungi canale corrente ai preferiti")
        self.add_btn.setMaximumWidth(36)
        self.add_btn.setMaximumHeight(32)
        self.add_btn.clicked.connect(self._on_add_current)
        layout.addWidget(self.add_btn)

    def set_channels(self, channels: List[Dict]):
        """channels: list of dicts with 'channel_id', 'display_name', 'channel_name'"""
        self._channels = channels
        self._rebuild_buttons()

    def set_current_channel(self, channel_id: int, channel_name: str = ""):
        self._current_channel_id = channel_id
        self._update_button_styles()
        # Show/hide add button if current is not in favorites
        fav_ids = {ch['channel_id'] for ch in self._channels}
        self.add_btn.setVisible(channel_id not in fav_ids and channel_id != 0)
        self.add_btn.setToolTip(f"Aggiungi '{channel_name}' ai preferiti")
        self._pending_add_name = channel_name
        self._pending_add_id = channel_id

    def _rebuild_buttons(self):
        # Clear existing buttons
        for btn in self._buttons.values():
            self.container_layout.removeWidget(btn)
            btn.deleteLater()
        self._buttons.clear()

        if not self._channels:
            placeholder = QLabel("Nessun canale preferito")
            placeholder.setStyleSheet("color: #888; font-style: italic;")
            self.container_layout.addWidget(placeholder)
            self._placeholder = placeholder
            return
        else:
            if hasattr(self, '_placeholder'):
                self._placeholder.deleteLater()
                delattr(self, '_placeholder')

        for ch in self._channels:
            btn = QPushButton(ch.get('display_name', ch.get('channel_name', str(ch['channel_id']))))
            btn.setCheckable(True)
            btn.setMaximumHeight(32)
            btn.setStyleSheet(self._default_button_style())
            btn.setToolTip(f"ID: {ch['channel_id']}")
            btn.clicked.connect(self._make_click_handler(ch['channel_id'], ch.get('display_name', ch.get('channel_name', ''))))
            self._buttons[ch['channel_id']] = btn
            self.container_layout.addWidget(btn)

        self.container_layout.addStretch()
        self._update_button_styles()

    def _make_click_handler(self, channel_id: int, channel_name: str) -> Callable:
        def handler():
            self.channel_selected.emit(channel_id, channel_name)
        return handler

    def _update_button_styles(self):
        for ch_id, btn in self._buttons.items():
            if ch_id == self._current_channel_id:
                btn.setChecked(True)
                btn.setStyleSheet(self._active_button_style())
            else:
                btn.setChecked(False)
                btn.setStyleSheet(self._default_button_style())

    def _default_button_style(self) -> str:
        return """
            QPushButton {
                background-color: #333;
                color: #eee;
                border: 1px solid #555;
                border-radius: 12px;
                padding: 4px 12px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #444;
                border: 1px solid #777;
            }
        """

    def _active_button_style(self) -> str:
        return """
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: 1px solid #1976D2;
                border-radius: 12px;
                padding: 4px 12px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #42A5F5;
            }
        """

    def _on_add_current(self):
        if hasattr(self, '_pending_add_id') and self._pending_add_id:
            name = getattr(self, '_pending_add_name', '')
            self.add_to_favorites_requested.emit(self._pending_add_id, name)

    def add_channel(self, channel_id: int, channel_name: str, display_name: str = ""):
        if not display_name:
            display_name = channel_name
        # Check if already exists
        for ch in self._channels:
            if ch['channel_id'] == channel_id:
                return
        self._channels.append({
            'channel_id': channel_id,
            'channel_name': channel_name,
            'display_name': display_name,
        })
        self._rebuild_buttons()
        self.set_current_channel(self._current_channel_id)
