"""
Test per file_service.py — extract_original_filename.
"""

from gui.services.file_service import extract_original_filename


# ─── Estensioni singole ─────────────────────────────────────────────

class TestSingleExtension:
    """Test con estensione singola (.txt, .pdf, etc.)."""

    def test_simple_txt(self):
        assert extract_original_filename("readme.txt") == "readme.txt"

    def test_simple_pdf(self):
        assert extract_original_filename("report.pdf") == "report.pdf"

    def test_simple_jpg(self):
        assert extract_original_filename("foto.jpg") == "foto.jpg"

    def test_single_char_extension(self):
        assert extract_original_filename("main.c") == "main.c"

    def test_long_extension_6_chars(self):
        assert extract_original_filename("file.tgzABC") == "file.tgzABC"

    def test_extension_too_long_7_chars(self):
        """Estensione di 7+ caratteri non è valida."""
        assert extract_original_filename("data.too_long") == ""

    def test_filename_with_spaces(self):
        assert extract_original_filename("my document final.pdf") == "my document final.pdf"

    def test_filename_with_underscores(self):
        assert extract_original_filename("backup_2026_06.tar") == "backup_2026_06.tar"

    def test_filename_with_hyphens(self):
        assert extract_original_filename("my-file-v2.zip") == "my-file-v2.zip"

    def test_uppercase_extension(self):
        assert extract_original_filename("README.TXT") == "README.TXT"

    def test_mixed_case_extension(self):
        assert extract_original_filename("notes.DocX") == "notes.DocX"

    def test_deb_package(self):
        assert extract_original_filename("app_.deb") == "app_.deb"


# ─── Doppie e triple estensioni ─────────────────────────────────────

class TestDoubleExtension:
    """Test con estensioni multiple (.tar.gz, .min.js, .a.b.c)."""

    def test_tar_gz(self):
        assert extract_original_filename("backup.tar.gz") == "backup.tar.gz"

    def test_tar_xz(self):
        assert extract_original_filename("archive.tar.xz") == "archive.tar.xz"

    def test_min_js(self):
        assert extract_original_filename("jquery.min.js") == "jquery.min.js"

    def test_min_css(self):
        assert extract_original_filename("styles.min.css") == "styles.min.css"

    def test_tar_bz2(self):
        assert extract_original_filename("package.tar.bz2") == "package.tar.bz2"

    def test_triple_extension(self):
        assert extract_original_filename("lib.so.1.2") == "lib.so.1.2"


# ─── Casi limite ────────────────────────────────────────────────────

class TestEdgeCases:
    """Test casi limite: stringa vuota, spazi, slash, newline."""

    def test_empty_string(self):
        assert extract_original_filename("") == ""

    def test_only_spaces(self):
        assert extract_original_filename("   ") == ""

    def test_strips_leading_trailing_spaces(self):
        assert extract_original_filename("  file.txt  ") == "file.txt"

    def test_newline_rejected(self):
        assert extract_original_filename("file.txt\nmalicious") == ""

    def test_slash_rejected(self):
        assert extract_original_filename("dir/file.txt") == ""

    def test_backslash_rejected(self):
        assert extract_original_filename("dir\\file.txt") == ""

    def test_text_without_extension(self):
        assert extract_original_filename("Just some text here") == ""

    def test_text_with_extension_in_middle(self):
        """Solo l'estensione finale conta per la validazione."""
        # "file.txt is here" non finisce con estensione → vuoto
        assert extract_original_filename("file.txt is here") == ""

    def test_dotfile(self):
        """File che iniziano con punto (es. .gitignore) non hanno estensione."""
        assert extract_original_filename(".gitignore") == ""

    def test_only_extension(self):
        """Solo estensione (.txt) è valido come nome file."""
        assert extract_original_filename(".txt") == ".txt"

    def test_double_dot(self):
        """Doppio punto: 'a..b' — la regex matcha '.b' alla fine."""
        assert extract_original_filename("a..b") == "a..b"
