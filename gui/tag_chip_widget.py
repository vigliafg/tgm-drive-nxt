"""TagChipWidget — Widget compatto che mostra i tag come chip/pill cliccabili in orizzontale.

Usa un FlowLayout (adattato dagli esempi Qt) per il wrapping automatico su più righe.
"""

from PyQt6.QtWidgets import QWidget, QLabel, QPushButton, QLayout, QSizePolicy, QStyle
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QSize, QPoint
from PyQt6.QtGui import QFont
from typing import List, Dict


# ─── FlowLayout: layout orizzontale con wrapping multi-riga ──────────────
# Adattato dagli esempi ufficiali Qt:
# https://doc.qt.io/qt-6/qtwidgets-layouts-flowlayout-example.html

class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, h_spacing=4, v_spacing=4):
        super().__init__(parent)
        self._items = []
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing
        self.setContentsMargins(margin, margin, margin, margin)

    def __del__(self):
        while self._items:
            item = self._items.pop()
            del item

    def addItem(self, item):
        self._items.append(item)

    def addWidget(self, w):
        item = super().addWidget(w)
        return item

    def horizontalSpacing(self):
        return self._h_spacing

    def verticalSpacing(self):
        return self._v_spacing

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), apply_geometry=False)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, apply_geometry=True)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(
            margins.left() + margins.right(),
            margins.top() + margins.bottom(),
        )
        return size

    def _do_layout(self, rect, apply_geometry):
        margins = self.contentsMargins()
        effective_rect = rect.adjusted(
            margins.left(), margins.top(),
            -margins.right(), -margins.bottom(),
        )
        x = effective_rect.x()
        y = effective_rect.y()
        line_height = 0

        for item in self._items:
            wid = item.widget()
            space_x = self._h_spacing
            space_y = self._v_spacing
            if wid is not None:
                space_x += wid.style().layoutSpacing(
                    QSizePolicy.ControlType.PushButton,
                    QSizePolicy.ControlType.PushButton,
                    Qt.Orientation.Horizontal,
                )
                space_y += wid.style().layoutSpacing(
                    QSizePolicy.ControlType.PushButton,
                    QSizePolicy.ControlType.PushButton,
                    Qt.Orientation.Vertical,
                )

            next_x = x + item.sizeHint().width() + space_x
            if next_x - space_x > effective_rect.right() and line_height > 0:
                x = effective_rect.x()
                y = y + line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0

            if apply_geometry:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))

            x = next_x
            line_height = max(line_height, item.sizeHint().height())

        return y + line_height - rect.y() + margins.bottom()


# ─── TagChipWidget ──────────────────────────────────────────────────────────

CHIP_STYLE_NORMAL = (
    "QLabel {"
    "  color: #aaa;"
    "  background-color: transparent;"
    "  border: 1px solid #555;"
    "  border-radius: 10px;"
    "  padding: 3px 10px;"
    "  font-size: 12px;"
    "}"
    "QLabel:hover {"
    "  background-color: #444;"
    "  color: #ddd;"
    "}"
)

CHIP_STYLE_SELECTED = (
    "QLabel {"
    "  color: #1e1e2e;"
    "  background-color: #89b4fa;"
    "  border: 1px solid #74c7ec;"
    "  border-radius: 10px;"
    "  padding: 3px 10px;"
    "  font-size: 12px;"
    "  font-weight: bold;"
    "}"
    "QLabel:hover {"
    "  background-color: #74c7ec;"
    "}"
)

CHIP_STYLE_ALL_NORMAL = (
    "QLabel {"
    "  color: #888;"
    "  background-color: transparent;"
    "  border: 1px solid #555;"
    "  border-radius: 10px;"
    "  padding: 3px 10px;"
    "  font-size: 12px;"
    "  font-style: italic;"
    "}"
    "QLabel:hover {"
    "  background-color: #444;"
    "  color: #ccc;"
    "}"
)

CHIP_STYLE_ALL_SELECTED = (
    "QLabel {"
    "  color: #cdd6f4;"
    "  background-color: #555;"
    "  border: 1px solid #777;"
    "  border-radius: 10px;"
    "  padding: 3px 10px;"
    "  font-size: 12px;"
    "  font-style: italic;"
    "  font-weight: bold;"
    "}"
)


class TagChipWidget(QWidget):
    """Widget compatto che mostra i tag come chip/pill cliccabili orizzontali.
    Il layout va a capo automaticamente se ci sono troppi tag.
    """

    tag_clicked = pyqtSignal(str)     # emette il nome del tag cliccato (\"\" per reset)
    manage_requested = pyqtSignal()   # emesso al clic su [+]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_tag: str = ""
        self._chips: Dict[str, QLabel] = {}
        self._build_ui()

    def _build_ui(self):
        self._flow = FlowLayout(self, margin=6, h_spacing=6, v_spacing=4)
        self.setStyleSheet(
            "TagChipWidget {"
            "  background-color: #252535;"
            "  border: 1px solid #3a3a4a;"
            "  border-radius: 6px;"
            "}"
        )

        # Il pulsante [+] viene aggiunto in fondo nel metodo set_tags()

    def set_tags(self, tags: list):
        """Ricostruisce i chip. `tags` è la lista ordinata di nomi tag."""
        # Rimuovi tutti i chip esistenti
        for chip in self._chips.values():
            self._flow.removeWidget(chip)
            chip.deleteLater()
        self._chips.clear()

        # Rimuovi il pulsante [+] esistente se presente
        if hasattr(self, '_manage_btn') and self._manage_btn:
            self._flow.removeWidget(self._manage_btn)

        # Chip "Tutti i file"
        all_chip = self._make_chip("🏠 Tutti i file", "", is_all=True)
        self._flow.addWidget(all_chip)

        # Chip per ogni tag
        for tag_name in tags:
            chip = self._make_chip(f"🏷️ {tag_name}", tag_name, is_all=False)
            self._flow.addWidget(chip)

        # Pulsante gestione in fondo
        self._manage_btn = QPushButton("➕")
        self._manage_btn.setFixedSize(28, 28)
        self._manage_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._manage_btn.setStyleSheet(
            "QPushButton {"
            "  background: transparent; color: #888; border: 1px solid #555;"
            "  border-radius: 14px; font-size: 14px;"
            "}"
            "QPushButton:hover { color: #fff; border-color: #89b4fa; }"
        )
        self._manage_btn.setToolTip("Gestisci tag")
        self._manage_btn.clicked.connect(self.manage_requested.emit)
        self._flow.addWidget(self._manage_btn)

        self._update_styles()

    def _make_chip(self, label: str, tag_value: str, is_all: bool = False) -> QLabel:
        chip = QLabel(label)
        chip.setCursor(Qt.CursorShape.PointingHandCursor)
        chip.mousePressEvent = lambda e, tv=tag_value: self._on_chip_click(tv)
        self._chips[tag_value] = chip
        return chip

    def _on_chip_click(self, tag_value: str):
        if self._selected_tag == tag_value:
            # Clic sullo stesso tag → deseleziona (torna a "Tutti i file")
            self._selected_tag = ""
            self.tag_clicked.emit("")
        else:
            self._selected_tag = tag_value
            self.tag_clicked.emit(tag_value)
        self._update_styles()

    def _update_styles(self):
        for tag_value, chip in self._chips.items():
            is_selected = (tag_value == self._selected_tag)
            if tag_value == "":
                chip.setStyleSheet(CHIP_STYLE_ALL_SELECTED if is_selected else CHIP_STYLE_ALL_NORMAL)
            else:
                chip.setStyleSheet(CHIP_STYLE_SELECTED if is_selected else CHIP_STYLE_NORMAL)
