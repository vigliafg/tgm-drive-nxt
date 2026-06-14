"""
Test per tag_service.py — PendingTagManager.
"""

from gui.services.tag_service import PendingTagManager


# ─── Base: add + pop ─────────────────────────────────────────────

class TestAddPop:
    """Test del flusso base add → pop."""

    def test_add_single_tag(self):
        m = PendingTagManager()
        m.add("foto.jpg", "personale")
        assert m.pop("foto.jpg") == "personale"

    def test_pop_removes_tag(self):
        """Dopo pop, il tag non c'è più."""
        m = PendingTagManager()
        m.add("doc.pdf", "lavoro")
        m.pop("doc.pdf")
        assert m.pop("doc.pdf") == ""

    def test_pop_without_add(self):
        """Pop su file senza tag pendenti restituisce stringa vuota."""
        m = PendingTagManager()
        assert m.pop("inesistente.txt") == ""

    def test_pop_empty_manager(self):
        """Manager vuoto, pop restituisce sempre vuoto."""
        m = PendingTagManager()
        assert m.pop("a") == ""
        assert m.pop("b") == ""


# ─── Tag multipli per stesso file ─────────────────────────────────

class TestMultipleTags:
    """Test con più tag pendenti per lo stesso filename."""

    def test_two_tags_same_file(self):
        m = PendingTagManager()
        m.add("report.pdf", "lavoro")
        m.add("report.pdf", "progetti")
        assert m.pop("report.pdf") == "lavoro"
        assert m.pop("report.pdf") == "progetti"
        assert m.pop("report.pdf") == ""

    def test_three_tags_same_file(self):
        m = PendingTagManager()
        m.add("a.txt", "1")
        m.add("a.txt", "2")
        m.add("a.txt", "3")
        assert m.pop("a.txt") == "1"
        assert m.pop("a.txt") == "2"
        assert m.pop("a.txt") == "3"
        assert m.pop("a.txt") == ""

    def test_interleaved_add_pop(self):
        """Add e pop alternati sullo stesso file."""
        m = PendingTagManager()
        m.add("file.dat", "alpha")
        assert m.pop("file.dat") == "alpha"
        m.add("file.dat", "beta")
        assert m.pop("file.dat") == "beta"
        assert m.pop("file.dat") == ""


# ─── Tag vuoti / None ─────────────────────────────────────────────

class TestEmptyTag:
    """Test comportamento con tag vuoto o stringa vuota."""

    def test_add_empty_string_ignored(self):
        """Tag vuoto non viene registrato."""
        m = PendingTagManager()
        m.add("file.txt", "")
        assert m.pop("file.txt") == ""

    def test_add_only_empty_tags(self):
        """Solo tag vuoti → manager è vuoto."""
        m = PendingTagManager()
        m.add("a.txt", "")
        m.add("b.txt", "")
        assert m.pop("a.txt") == ""
        assert m.pop("b.txt") == ""


# ─── File multipli ────────────────────────────────────────────────

class TestMultipleFiles:
    """Test con più file diversi."""

    def test_different_files(self):
        m = PendingTagManager()
        m.add("a.pdf", "lavoro")
        m.add("b.jpg", "personale")
        m.add("c.xlsx", "progetti")
        assert m.pop("a.pdf") == "lavoro"
        assert m.pop("b.jpg") == "personale"
        assert m.pop("c.xlsx") == "progetti"

    def test_different_files_interleaved(self):
        """Pop in ordine diverso dall'add."""
        m = PendingTagManager()
        m.add("a.pdf", "lavoro")
        m.add("b.jpg", "personale")
        assert m.pop("b.jpg") == "personale"
        m.add("a.pdf", "extra")
        assert m.pop("a.pdf") == "lavoro"
        assert m.pop("a.pdf") == "extra"
        assert m.pop("a.pdf") == ""

    def test_files_dont_interfere(self):
        """I tag di un file non influenzano gli altri."""
        m = PendingTagManager()
        m.add("a.txt", "tag_a1")
        m.add("a.txt", "tag_a2")
        m.add("b.txt", "tag_b")
        assert m.pop("b.txt") == "tag_b"
        assert m.pop("a.txt") == "tag_a1"
        assert m.pop("a.txt") == "tag_a2"


# ─── Edge cases ───────────────────────────────────────────────────

class TestEdgeCases:
    """Test casi limite: nomi file speciali, unicode."""

    def test_filename_with_spaces(self):
        m = PendingTagManager()
        m.add("my file.txt", "test")
        assert m.pop("my file.txt") == "test"

    def test_unicode_filename(self):
        m = PendingTagManager()
        m.add("caffè.pdf", "☕")
        assert m.pop("caffè.pdf") == "☕"

    def test_unicode_tag(self):
        m = PendingTagManager()
        m.add("doc.pdf", "lavoro ✨")
        assert m.pop("doc.pdf") == "lavoro ✨"

    def test_empty_filename(self):
        """Filename vuoto è trattato come chiave normale."""
        m = PendingTagManager()
        m.add("", "tag")
        assert m.pop("") == "tag"
        assert m.pop("") == ""

    def test_large_number_of_tags(self):
        """Molti tag sullo stesso file."""
        m = PendingTagManager()
        for i in range(100):
            m.add("bulk.dat", f"tag_{i}")
        for i in range(100):
            assert m.pop("bulk.dat") == f"tag_{i}"
        assert m.pop("bulk.dat") == ""
