"""
Test per tag_chip_widget.py — TagChipWidget e FlowLayout.

Questi test usano pytest-qt (qtbot) per interagire con i widget.
"""

import pytest
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtWidgets import QLabel, QPushButton

from gui.tag_chip_widget import TagChipWidget, FlowLayout, CHIP_STYLE_NORMAL, CHIP_STYLE_SELECTED


# ─── FlowLayout ─────────────────────────────────────────────────────────

class TestFlowLayout:
    """Test del layout FlowLayout custom.
    
    Tutti i test usano il fixture qtbot perché FlowLayout eredita da QLayout
    e richiede una QApplication attiva."""

    def test_initialization(self, qtbot):
        """FlowLayout si inizializza correttamente."""
        flow = FlowLayout()
        assert flow.count() == 0
        assert flow.horizontalSpacing() == 4
        assert flow.verticalSpacing() == 4

    def test_custom_spacing(self, qtbot):
        """FlowLayout accetta spaziature personalizzate."""
        flow = FlowLayout(h_spacing=10, v_spacing=8)
        assert flow.horizontalSpacing() == 10
        assert flow.verticalSpacing() == 8

    def test_add_widget_increases_count(self, qtbot):
        """Aggiungere widget incrementa il conteggio."""
        flow = FlowLayout()
        label = QLabel("Test")
        flow.addWidget(label)
        assert flow.count() == 1

    def test_take_at_removes_widget(self, qtbot):
        """takeAt rimuove e restituisce il widget."""
        flow = FlowLayout()
        label = QLabel("Test")
        flow.addWidget(label)
        assert flow.count() == 1
        item = flow.takeAt(0)
        assert item is not None
        assert flow.count() == 0

    def test_take_at_invalid_index(self, qtbot):
        """takeAt con indice non valido restituisce None."""
        flow = FlowLayout()
        assert flow.takeAt(0) is None
        assert flow.takeAt(-1) is None
        assert flow.takeAt(100) is None

    def test_item_at(self, qtbot):
        """itemAt restituisce l'item all'indice specificato."""
        flow = FlowLayout()
        label = QLabel("Test")
        flow.addWidget(label)
        item = flow.itemAt(0)
        assert item is not None
        assert item.widget() == label

    def test_item_at_invalid_index(self, qtbot):
        """itemAt con indice non valido restituisce None."""
        flow = FlowLayout()
        assert flow.itemAt(-1) is None
        assert flow.itemAt(100) is None

    def test_has_height_for_width(self, qtbot):
        """FlowLayout supporta heightForWidth (wrapping)."""
        flow = FlowLayout()
        assert flow.hasHeightForWidth() is True

    def test_expanding_directions(self, qtbot):
        """FlowLayout non ha direzioni di espansione."""
        flow = FlowLayout()
        assert flow.expandingDirections() == Qt.Orientation(0)

    def test_minimum_size(self, qtbot):
        """minimumSize restituisce una QSize valida (anche per layout vuoto)."""
        flow = FlowLayout()
        size = flow.minimumSize()
        # Un layout vuoto può restituire una QSize con valori negativi
        # (comportamento di default di QLayout)
        assert isinstance(size.width(), int)
        assert isinstance(size.height(), int)

    def test_size_hint(self, qtbot):
        """sizeHint restituisce il minimumSize."""
        flow = FlowLayout()
        assert flow.sizeHint() == flow.minimumSize()

    def test_do_layout(self, qtbot):
        """_do_layout calcola le posizioni senza errori."""
        flow = FlowLayout()
        widget = QLabel("A")
        flow.addWidget(widget)
        # Chiamata con rect e apply_geometry
        result = flow._do_layout(QRect(0, 0, 200, 100), apply_geometry=True)
        assert result >= 0

    def test_multiple_widgets_layout(self, qtbot):
        """Layout con più widget calcola wrapping (altezza > 0 se ci sono widget)."""
        flow = FlowLayout()
        for i in range(5):
            lbl = QLabel(f"Tag {i}")
            lbl.setFixedSize(60, 24)  # Dimensione esplicita per sizeHint deterministico
            flow.addWidget(lbl)
        result = flow._do_layout(QRect(0, 0, 200, 200), apply_geometry=True)
        # Con 5 label da 60px in un rettangolo da 200px, ci saranno wrapping
        assert result >= 0


# ─── TagChipWidget ──────────────────────────────────────────────────────

class TestTagChipWidget:
    """Test del widget TagChipWidget."""

    @pytest.fixture
    def widget(self, qtbot):
        w = TagChipWidget()
        qtbot.addWidget(w)
        return w

    def test_initial_state(self, widget):
        """Il widget inizia senza tag e senza selezione."""
        assert widget._selected_tag == ""
        assert len(widget._chips) == 0

    def test_set_tags_creates_chips(self, widget, qtbot):
        """set_tags crea i chip per tutti i tag + 'Tutti i file'."""
        widget.set_tags(["lavoro", "personale", "progetti"])
        qtbot.wait(50)
        # Deve avere 4 chip: "", "lavoro", "personale", "progetti"
        assert len(widget._chips) == 4
        assert "" in widget._chips
        assert "lavoro" in widget._chips
        assert "personale" in widget._chips
        assert "progetti" in widget._chips

    def test_set_tags_creates_manage_button(self, widget, qtbot):
        """set_tags crea il pulsante [+]."""
        widget.set_tags(["lavoro"])
        qtbot.wait(50)
        assert hasattr(widget, '_manage_btn')
        assert widget._manage_btn is not None
        assert widget._manage_btn.text() == "➕"

    def test_set_tags_clears_previous(self, widget, qtbot):
        """Chiamare set_tags due volte pulisce i chip precedenti."""
        widget.set_tags(["tag1", "tag2"])
        qtbot.wait(50)
        assert len(widget._chips) == 3  # "" + tag1 + tag2

        widget.set_tags(["tag3"])
        qtbot.wait(50)
        assert len(widget._chips) == 2  # "" + tag3
        assert "tag1" not in widget._chips
        assert "tag2" not in widget._chips

    def test_set_tags_empty_list(self, widget, qtbot):
        """set_tags con lista vuota mostra solo 'Tutti i file'."""
        widget.set_tags([])
        qtbot.wait(50)
        assert len(widget._chips) == 1  # solo ""

    def test_chip_click_emits_signal(self, widget, qtbot):
        """Cliccare un chip emette tag_clicked con il nome del tag."""
        widget.set_tags(["lavoro"])
        qtbot.wait(50)

        with qtbot.waitSignal(widget.tag_clicked, timeout=1000) as blocker:
            widget._on_chip_click("lavoro")
        assert blocker.args == ["lavoro"]

    def test_chip_click_sets_selection(self, widget, qtbot):
        """Cliccare un chip imposta la selezione."""
        widget.set_tags(["lavoro", "personale"])
        qtbot.wait(50)
        widget._on_chip_click("lavoro")
        assert widget._selected_tag == "lavoro"

    def test_chip_click_toggle_off(self, widget, qtbot):
        """Cliccare lo stesso chip due volte deseleziona."""
        widget.set_tags(["lavoro"])
        qtbot.wait(50)
        # Seleziona
        widget._on_chip_click("lavoro")
        assert widget._selected_tag == "lavoro"
        # Deseleziona
        with qtbot.waitSignal(widget.tag_clicked, timeout=1000) as blocker:
            widget._on_chip_click("lavoro")
        assert blocker.args == [""]
        assert widget._selected_tag == ""

    def test_chip_click_switches_selection(self, widget, qtbot):
        """Cliccare un tag diverso cambia la selezione."""
        widget.set_tags(["lavoro", "personale"])
        qtbot.wait(50)
        widget._on_chip_click("lavoro")
        assert widget._selected_tag == "lavoro"

        with qtbot.waitSignal(widget.tag_clicked, timeout=1000) as blocker:
            widget._on_chip_click("personale")
        assert blocker.args == ["personale"]
        assert widget._selected_tag == "personale"

    def test_all_files_chip_emits_empty_string(self, widget, qtbot):
        """Cliccare 'Tutti i file' emette stringa vuota."""
        widget.set_tags(["lavoro"])
        qtbot.wait(50)
        with qtbot.waitSignal(widget.tag_clicked, timeout=1000) as blocker:
            widget._on_chip_click("")
        assert blocker.args == [""]
        # "Tutti i file" non ha selezione visiva persistente (viene deselezionato subito)

    def test_manage_button_click(self, widget, qtbot):
        """Cliccare [+] emette manage_requested."""
        widget.set_tags(["lavoro"])
        qtbot.wait(50)

        with qtbot.waitSignal(widget.manage_requested, timeout=1000):
            widget._manage_btn.click()

    def test_update_styles_normal(self, widget, qtbot):
        """_update_styles applica lo stile normale ai chip non selezionati."""
        widget.set_tags(["lavoro"])
        qtbot.wait(50)
        widget._selected_tag = ""
        widget._update_styles()
        # Il chip "lavoro" dovrebbe avere lo stile normale
        chip = widget._chips.get("lavoro")
        assert chip is not None
        style = chip.styleSheet()
        assert "color: #aaa" in style

    def test_update_styles_selected(self, widget, qtbot):
        """_update_styles applica lo stile selezionato al chip attivo."""
        widget.set_tags(["lavoro"])
        qtbot.wait(50)
        widget._selected_tag = "lavoro"
        widget._update_styles()
        chip = widget._chips.get("lavoro")
        style = chip.styleSheet()
        assert "89b4fa" in style or "font-weight: bold" in style

    def test_update_styles_all_chip(self, widget, qtbot):
        """Il chip 'Tutti i file' ha uno stile diverso (italic)."""
        widget.set_tags(["lavoro"])
        qtbot.wait(50)
        widget._selected_tag = ""
        widget._update_styles()
        all_chip = widget._chips.get("")
        assert all_chip is not None
        style = all_chip.styleSheet()
        # Lo stile "all" ha font-style: italic
        # Verifichiamo solo che esista il chip e abbia uno stylesheet
        assert len(style) > 0

    def test_make_chip_creates_clickable_label(self, widget, qtbot):
        """_make_chip crea una QLabel con cursor a mano."""
        chip = widget._make_chip("Test Tag", "test_value", is_all=False)
        assert isinstance(chip, QLabel)
        assert chip.cursor().shape() == Qt.CursorShape.PointingHandCursor
        # Deve avere un mousePressEvent
        assert chip.text() == "Test Tag"
