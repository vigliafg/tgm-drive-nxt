"""
Test per database.py — CRUD, search, tags, channels, favorites, migrazioni.

Questo è il modulo di test più importante: la logica del database è la spina dorsale
dell'applicazione e va testata esaustivamente.
"""

import sqlite3
from datetime import datetime

import pytest

from database import Database, FileRecord


# ─── Inizializzazione e schema ─────────────────────────────────────────

class TestDatabaseInit:
    """Test dell'inizializzazione del database e creazione schema."""

    def test_init_creates_tables(self, memory_db):
        """Il costruttore deve creare tutte le tabelle necessarie."""
        conn = memory_db._connect()
        tables = [
            row[0] for row in
            conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        ]
        conn.close()
        assert "files" in tables
        assert "channels" in tables
        assert "favorite_channels" in tables
        assert "tags" in tables

    def test_init_creates_indexes(self, memory_db):
        """Devono esistere gli indici per filename, tags, channel_id."""
        conn = memory_db._connect()
        indexes = [
            row[1] for row in
            conn.execute("SELECT * FROM sqlite_master WHERE type='index'").fetchall()
        ]
        conn.close()
        assert "idx_filename" in indexes
        assert "idx_tags" in indexes
        assert "idx_channel_id" in indexes

    def test_init_is_idempotent(self, memory_db):
        """Chiamare _init_db più volte non deve causare errori."""
        memory_db._init_db()
        memory_db._init_db()
        # Deve arrivare qui senza eccezioni
        tables = [
            row[0] for row in
            memory_db._connect().execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
        assert "files" in tables

    def test_custom_db_path(self, tmp_path):
        """Il database può essere creato in un percorso personalizzato."""
        db_path = tmp_path / "test.db"
        db = Database(db_path=str(db_path))
        assert db_path.exists()
        db.clear_all()

    def test_file_record_dataclass(self):
        """Verifica che FileRecord sia creabile con tutti i campi."""
        record = FileRecord(
            id=1, message_id=100, filename="test.txt", size=1024,
            mime_type="text/plain", upload_date="2026-01-01T00:00:00",
            tags="test", local_path="/tmp/test.txt", telegram_path=None,
            channel_id=-1001111111111, original_filename="original.txt"
        )
        assert record.id == 1
        assert record.message_id == 100
        assert record.filename == "test.txt"
        assert record.size == 1024
        assert record.mime_type == "text/plain"
        assert record.tags == "test"
        assert record.channel_id == -1001111111111
        assert record.original_filename == "original.txt"


# ─── Inserimento e recupero file ───────────────────────────────────────

class TestFileOperations:
    """Test delle operazioni CRUD sui file."""

    def test_insert_file(self, memory_db):
        """Inserimento base di un file."""
        rowid = memory_db.insert_file(
            message_id=1001, filename="test.pdf", size=1024,
            mime_type="application/pdf", tags="lavoro",
            channel_id=-1001111111111, original_filename="report.pdf"
        )
        assert rowid > 0

    def test_get_file_by_message_id(self, memory_db):
        """Recupero di un file per message_id."""
        memory_db.insert_file(
            message_id=2001, filename="doc.txt", size=500,
            mime_type="text/plain", tags="", channel_id=-1001111111111
        )
        file = memory_db.get_file_by_message_id(2001)
        assert file is not None
        assert file.filename == "doc.txt"
        assert file.message_id == 2001
        assert file.size == 500

    def test_get_file_by_message_id_not_found(self, memory_db):
        """Recupero di un message_id inesistente -> None."""
        file = memory_db.get_file_by_message_id(99999)
        assert file is None

    def test_insert_file_upsert(self, memory_db):
        """ON CONFLICT: re-inserire stesso message_id aggiorna il record."""
        memory_db.insert_file(
            message_id=3001, filename="old.pdf", size=100,
            mime_type="application/pdf", tags="old", channel_id=-1001111111111
        )
        memory_db.insert_file(
            message_id=3001, filename="new.pdf", size=200,
            mime_type="application/pdf", tags="new", channel_id=-1002222222222,
            original_filename="updated.pdf"
        )
        file = memory_db.get_file_by_message_id(3001)
        assert file.filename == "new.pdf"
        assert file.size == 200
        # Tags: la logica ON CONFLICT preserva i tag se il nuovo è vuoto
        assert file.tags == "new"
        assert file.channel_id == -1002222222222
        assert file.original_filename == "updated.pdf"

    def test_insert_file_preserves_tags_on_empty_update(self, memory_db):
        """Se il nuovo insert ha tags='', deve preservare i tag esistenti."""
        memory_db.insert_file(
            message_id=4001, filename="keep.pdf", size=100,
            mime_type="application/pdf", tags="importante", channel_id=-1001111111111
        )
        memory_db.insert_file(
            message_id=4001, filename="keep.pdf", size=200,
            mime_type="application/pdf", tags="", channel_id=-1001111111111
        )
        file = memory_db.get_file_by_message_id(4001)
        assert file.tags == "importante"  # Preservato dal CASE WHEN

    def test_get_all_files(self, populated_db):
        """get_all_files senza filtri restituisce tutti i file."""
        files = populated_db.get_all_files(channel_id=0)
        assert len(files) == 4

    def test_get_all_files_filtered_by_channel(self, populated_db):
        """get_all_files con channel_id specifico."""
        files = populated_db.get_all_files(channel_id=-1001111111111)
        assert len(files) == 2
        for f in files:
            assert f.channel_id == -1001111111111

    def test_get_all_files_exclude_channel_zero(self, populated_db):
        """get_all_files con channel_id=-1 esclude quelli con channel_id=0."""
        files = populated_db.get_all_files(channel_id=-1)
        for f in files:
            assert f.channel_id != 0

    def test_delete_file(self, populated_db):
        """Eliminazione di un file per message_id."""
        assert populated_db.get_file_by_message_id(1001) is not None
        populated_db.delete_file(1001)
        assert populated_db.get_file_by_message_id(1001) is None

    def test_delete_file_nonexistent(self, populated_db):
        """Eliminazione di un file inesistente non causa errori."""
        populated_db.delete_file(99999)

    def test_clear_all(self, populated_db):
        """clear_all deve rimuovere tutti i file."""
        populated_db.clear_all()
        files = populated_db.get_all_files()
        assert len(files) == 0


# ─── Ricerca ────────────────────────────────────────────────────────────

class TestSearch:
    """Test della ricerca con LIKE e escape."""

    def test_search_exact_match(self, populated_db):
        """Ricerca per nome file esatto."""
        results = populated_db.search_files("documento_lavoro")
        assert len(results) == 1
        assert results[0].filename == "documento_lavoro.pdf"

    def test_search_partial_match(self, populated_db):
        """Ricerca per sottostringa."""
        results = populated_db.search_files("foto")
        assert len(results) == 1
        assert results[0].filename == "foto_vacanze.jpg"

    def test_search_multiple_terms_and(self, populated_db):
        """Ricerca con più termini (AND implicito)."""
        results = populated_db.search_files("foto jpg")
        assert len(results) >= 1

    def test_search_by_tag(self, populated_db):
        """Ricerca per tag (la colonna tags è inclusa nella ricerca)."""
        results = populated_db.search_files("lavoro")
        # Trova sia il file con tag "lavoro" che eventuali match nel nome
        assert len(results) >= 1

    def test_search_case_sensitive(self, populated_db):
        """La ricerca LIKE è case-insensitive? Dipende dal collation."""
        results = populated_db.search_files("LAVORO")
        # SQLite LIKE è case-insensitive per ASCII di default
        assert len(results) >= 1

    def test_search_empty_query(self, populated_db):
        """Query vuota restituisce tutti i file."""
        results = populated_db.search_files("", channel_id=0)
        assert len(results) == 4

    def test_search_with_underscore_escape(self, populated_db):
        """L'underscore (_) nei nomi file deve essere escaped."""
        db = populated_db
        db.insert_file(
            message_id=5001, filename="test_file.txt", size=100,
            mime_type="text/plain", tags="", channel_id=-1001111111111
        )
        # Cerca con underscore letterale — deve trovare il file esatto
        results = db.search_files("test_file")
        assert len(results) >= 1
        assert any(f.filename == "test_file.txt" for f in results)

    def test_search_with_percent_escape(self, populated_db):
        """Il percento (%) nei nomi file deve essere escaped."""
        db = populated_db
        db.insert_file(
            message_id=5002, filename="100%_complete.txt", size=100,
            mime_type="text/plain", tags="", channel_id=-1001111111111
        )
        results = db.search_files("100%")
        assert len(results) >= 1
        assert any(f.filename == "100%_complete.txt" for f in results)

    def test_search_no_results(self, populated_db):
        """Query senza match restituisce lista vuota."""
        results = populated_db.search_files("zzzz_nonexistent_zzzz")
        assert len(results) == 0

    def test_search_with_channel_filter(self, populated_db):
        """Ricerca con filtro canale."""
        results = populated_db.search_files("foto", channel_id=-1001111111111)
        assert len(results) == 1

    def test_search_exclude_channel_zero(self, populated_db):
        """Ricerca con channel_id=-1 esclude channel_id=0."""
        results = populated_db.search_files("foto", channel_id=-1)
        for f in results:
            assert f.channel_id != 0


# ─── Canali ─────────────────────────────────────────────────────────────

class TestChannels:
    """Test della tabella channels."""

    def test_insert_channel(self, memory_db):
        """Inserimento di un canale."""
        memory_db.insert_or_update_channel(-1001111111111, "Test Channel")
        channels = memory_db.get_channels()
        assert len(channels) == 1
        assert channels[0]["channel_id"] == -1001111111111
        assert channels[0]["channel_name"] == "Test Channel"

    def test_update_channel_name(self, memory_db):
        """Aggiornamento del nome di un canale esistente."""
        memory_db.insert_or_update_channel(-1001111111111, "Vecchio Nome")
        memory_db.insert_or_update_channel(-1001111111111, "Nuovo Nome")
        channels = memory_db.get_channels()
        assert len(channels) == 1
        assert channels[0]["channel_name"] == "Nuovo Nome"

    def test_get_channel_name(self, populated_db):
        """get_channel_name restituisce il nome o l'ID come stringa."""
        name = populated_db.get_channel_name(-1001111111111)
        assert name == "Canale Test 1"

    def test_get_channel_name_unknown(self, memory_db):
        """Canale sconosciuto -> restituisce l'ID come stringa."""
        name = memory_db.get_channel_name(-99999)
        assert name == "-99999"

    def test_get_files_channel_ids(self, populated_db):
        """get_files_channel_ids restituisce i channel_id distinti con file."""
        ids = populated_db.get_files_channel_ids()
        assert -1001111111111 in ids
        assert -1002222222222 in ids
        assert 0 not in ids  # channel_id=0 è escluso


# ─── Canali Preferiti ───────────────────────────────────────────────────

class TestFavoriteChannels:
    """Test della tabella favorite_channels."""

    def test_add_favorite_channel(self, memory_db):
        """Aggiunta di un canale preferito."""
        memory_db.add_favorite_channel(-1001111111111, "Test Channel")
        favs = memory_db.get_favorite_channels()
        assert len(favs) == 1
        assert favs[0]["channel_id"] == -1001111111111
        assert favs[0]["display_name"] == "Test Channel"

    def test_add_favorite_with_custom_display_name(self, memory_db):
        """Aggiunta con display_name personalizzato."""
        memory_db.add_favorite_channel(
            -1001111111111, "Test Channel", display_name="Mio Canale"
        )
        favs = memory_db.get_favorite_channels()
        assert favs[0]["display_name"] == "Mio Canale"

    def test_update_favorite_display_name(self, memory_db):
        """Aggiornamento del display_name."""
        memory_db.add_favorite_channel(-1001111111111, "Test", "Old Name")
        memory_db.update_favorite_channel_display_name(-1001111111111, "New Name")
        favs = memory_db.get_favorite_channels()
        assert favs[0]["display_name"] == "New Name"

    def test_remove_favorite_channel(self, memory_db):
        """Rimozione di un canale preferito."""
        memory_db.add_favorite_channel(-1001111111111, "Test")
        memory_db.remove_favorite_channel(-1001111111111)
        assert len(memory_db.get_favorite_channels()) == 0

    def test_set_favorite_channels(self, memory_db):
        """Sostituzione dell'intera lista preferiti."""
        memory_db.add_favorite_channel(-1001111111111, "Old")
        new_list = [
            {"channel_id": -1002222222222, "display_name": "New 1", "sort_order": 0},
            {"channel_id": -1003333333333, "display_name": "New 2", "sort_order": 1},
        ]
        memory_db.set_favorite_channels(new_list)
        favs = memory_db.get_favorite_channels()
        assert len(favs) == 2
        ids = {f["channel_id"] for f in favs}
        assert -1002222222222 in ids
        assert -1003333333333 in ids
        assert -1001111111111 not in ids

    def test_favorites_sorted_by_sort_order(self, memory_db):
        """I preferiti devono essere ordinati per sort_order."""
        memory_db.add_favorite_channel(-1003333333333, "C", sort_order=2)
        memory_db.add_favorite_channel(-1001111111111, "A", sort_order=0)
        memory_db.add_favorite_channel(-1002222222222, "B", sort_order=1)
        favs = memory_db.get_favorite_channels()
        assert favs[0]["channel_id"] == -1001111111111
        assert favs[1]["channel_id"] == -1002222222222
        assert favs[2]["channel_id"] == -1003333333333


# ─── Tags ───────────────────────────────────────────────────────────────

class TestTags:
    """Test del sistema di tagging."""

    def test_add_tag(self, memory_db):
        """Aggiunta di un tag."""
        tag_id = memory_db.add_tag("lavoro")
        tags = memory_db.get_tags()
        assert len(tags) == 1
        assert tags[0]["tag_name"] == "lavoro"

    def test_add_duplicate_tag_ignored(self, memory_db):
        """Tag duplicato viene ignorato (INSERT OR IGNORE)."""
        memory_db.add_tag("lavoro")
        memory_db.add_tag("lavoro")
        tags = memory_db.get_tags()
        assert len(tags) == 1

    def test_remove_tag(self, memory_db):
        """Rimozione di un tag."""
        tag_id = memory_db.add_tag("lavoro")
        assert len(memory_db.get_tags()) == 1
        memory_db.remove_tag(tag_id)
        assert len(memory_db.get_tags()) == 0

    def test_remove_tag_clears_files(self, populated_db):
        """Rimuovere un tag resetta i file che lo usano."""
        tags = populated_db.get_tags()
        lavoro_tag = next(t for t in tags if t["tag_name"] == "lavoro")
        file_before = populated_db.get_file_by_message_id(1001)
        assert file_before.tags == "lavoro"

        populated_db.remove_tag(lavoro_tag["tag_id"])
        file_after = populated_db.get_file_by_message_id(1001)
        assert file_after.tags == ""

    def test_rename_tag(self, memory_db):
        """Rinomina di un tag."""
        tag_id = memory_db.add_tag("lavoro")
        memory_db.rename_tag(tag_id, "ufficio")
        tags = memory_db.get_tags()
        assert tags[0]["tag_name"] == "ufficio"

    def test_rename_tag_updates_files(self, populated_db):
        """Rinominare un tag aggiorna anche i file che lo usano."""
        tags = populated_db.get_tags()
        lavoro_tag = next(t for t in tags if t["tag_name"] == "lavoro")
        populated_db.rename_tag(lavoro_tag["tag_id"], "ufficio")
        file = populated_db.get_file_by_message_id(1001)
        assert file.tags == "ufficio"

    def test_update_file_tag(self, populated_db):
        """Aggiornamento del tag di un singolo file."""
        populated_db.update_file_tag(1001, "archivio")
        file = populated_db.get_file_by_message_id(1001)
        assert file.tags == "archivio"

    def test_update_file_tag_to_empty(self, populated_db):
        """Rimozione del tag da un file impostandolo a stringa vuota."""
        file_before = populated_db.get_file_by_message_id(1001)
        assert file_before.tags == "lavoro"
        populated_db.update_file_tag(1001, "")
        file_after = populated_db.get_file_by_message_id(1001)
        assert file_after.tags == ""

    def test_get_files_by_tag(self, populated_db):
        """Filtraggio file per tag."""
        files = populated_db.get_files_by_tag("lavoro")
        assert len(files) == 1
        assert files[0].message_id == 1001

    def test_get_files_by_tag_cross_channel(self, populated_db):
        """get_files_by_tag senza channel_id restituisce tutti i canali."""
        # Aggiungiamo un secondo file con tag "lavoro" in un altro canale
        populated_db.insert_file(
            message_id=5001, filename="altro_lavoro.txt", size=100,
            mime_type="text/plain", tags="lavoro", channel_id=-1002222222222
        )
        files = populated_db.get_files_by_tag("lavoro", channel_id=0)
        assert len(files) == 2

    def test_get_files_by_tag_with_channel_filter(self, populated_db):
        """get_files_by_tag con filtro canale."""
        files = populated_db.get_files_by_tag("lavoro", channel_id=-1001111111111)
        assert len(files) == 1
        assert files[0].channel_id == -1001111111111

    def test_get_files_by_empty_tag(self, populated_db):
        """get_files_by_tag con tag vuoto trova i file senza tag."""
        files = populated_db.get_files_by_tag("")
        assert len(files) == 1
        assert files[0].message_id == 1004

    def test_set_tags_replaces_all(self, memory_db):
        """set_tags sostituisce l'intera lista tag."""
        memory_db.add_tag("old1")
        memory_db.add_tag("old2")
        new_tags = [
            {"tag_name": "new1", "sort_order": 0},
            {"tag_name": "new2", "sort_order": 1},
        ]
        memory_db.set_tags(new_tags)
        tags = memory_db.get_tags()
        assert len(tags) == 2
        tag_names = {t["tag_name"] for t in tags}
        assert tag_names == {"new1", "new2"}

    def test_tags_sorted_by_sort_order(self, memory_db):
        """I tag devono essere ordinati per sort_order, poi per nome."""
        memory_db.add_tag("C", sort_order=2)
        memory_db.add_tag("A", sort_order=0)
        memory_db.add_tag("B", sort_order=1)
        tags = memory_db.get_tags()
        assert tags[0]["tag_name"] == "A"
        assert tags[1]["tag_name"] == "B"
        assert tags[2]["tag_name"] == "C"


# ─── Migrazioni ─────────────────────────────────────────────────────────

class TestMigrations:
    """Test delle migrazioni automatiche dello schema."""

    def test_migration_adds_channel_id_column(self, tmp_path):
        """Se la tabella files esiste senza channel_id, viene aggiunto."""
        db_path = tmp_path / "legacy.db"
        # Crea un DB con schema vecchio (senza channel_id e original_filename)
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER UNIQUE,
                filename TEXT NOT NULL,
                size INTEGER DEFAULT 0,
                mime_type TEXT DEFAULT '',
                upload_date TEXT DEFAULT '',
                tags TEXT DEFAULT '',
                local_path TEXT,
                telegram_path TEXT
            )
        """)
        conn.commit()
        conn.close()

        db = Database(db_path=str(db_path))
        # Verifica che le colonne siano state aggiunte
        conn2 = db._connect()
        cols = [row[1] for row in conn2.execute("PRAGMA table_info(files)").fetchall()]
        conn2.close()
        assert "channel_id" in cols
        assert "original_filename" in cols

    def test_migration_does_not_break_existing_data(self, tmp_path):
        """La migrazione non deve corrompere i dati esistenti."""
        db_path = tmp_path / "legacy2.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER UNIQUE,
                filename TEXT NOT NULL,
                size INTEGER DEFAULT 0,
                mime_type TEXT DEFAULT '',
                upload_date TEXT DEFAULT '',
                tags TEXT DEFAULT '',
                local_path TEXT,
                telegram_path TEXT
            )
        """)
        conn.execute(
            "INSERT INTO files (message_id, filename, size, tags) VALUES (?, ?, ?, ?)",
            (999, "test_migration.txt", 500, "test")
        )
        conn.commit()
        conn.close()

        db = Database(db_path=str(db_path))
        file = db.get_file_by_message_id(999)
        assert file is not None
        assert file.filename == "test_migration.txt"
        assert file.size == 500
        assert file.tags == "test"
        assert file.channel_id == 0  # Default per la nuova colonna
        assert file.original_filename == ""  # Default per la nuova colonna


# ─── Performance ─────────────────────────────────────────────────────────

class TestDatabasePerformance:
    """Test base di performance: il DB deve gestire volumi ragionevoli."""

    def test_insert_many_files(self, memory_db):
        """Inserimento di 1000 file deve completarsi in tempi ragionevoli."""
        import time
        start = time.time()
        for i in range(1000):
            memory_db.insert_file(
                message_id=10000 + i,
                filename=f"file_{i:04d}.txt",
                size=1024,
                mime_type="text/plain",
                tags="test" if i % 2 == 0 else "",
                channel_id=-1001111111111,
            )
        elapsed = time.time() - start
        assert elapsed < 5.0  # 1000 insert in < 5 secondi
        assert len(memory_db.get_all_files()) == 1000

    def test_search_many_files(self, memory_db):
        """Ricerca su 500 file deve essere veloce."""
        for i in range(500):
            memory_db.insert_file(
                message_id=20000 + i,
                filename=f"search_file_{i:04d}.dat",
                size=100,
                mime_type="application/octet-stream",
                tags=f"tag_{i % 10}",
                channel_id=-1001111111111,
            )
        import time
        start = time.time()
        results = memory_db.search_files("search_file_0100")
        elapsed = time.time() - start
        assert len(results) >= 1
        assert elapsed < 1.0  # Ricerca in < 1 secondo
