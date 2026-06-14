"""
Fixture condivise per tutti i test di TGM Drive.
Centralizza la Dependency Injection: DB in-memory, client mockati, config temporanee.
"""

import sys
import os
from pathlib import Path

import pytest
from PyQt6.QtCore import QObject, pyqtSignal

# Assicura che la root del progetto sia nel path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import Database
from config import DEFAULT_CONFIG


# ─── Database in-memory ────────────────────────────────────────────────

@pytest.fixture
def memory_db(tmp_path):
    """Database SQLite su file temporaneo, pulito dopo ogni test.
    
    NOTA: usiamo un file su disco invece di :memory: perché SQLite
    crea un database in-memory SEPARATO per ogni connessione.
    I metodi del Database chiamano _connect() internamente, quindi
    ogni operazione vedrebbe un DB vuoto con :memory:.
    """
    db_path = tmp_path / "test.db"
    db = Database(db_path=str(db_path))
    yield db
    db.clear_all()
    # Cleanup: chiudi eventuali connessioni pendenti
    import gc
    gc.collect()


@pytest.fixture
def memory_db_path(tmp_path):
    """Restituisce il percorso a un database temporaneo (da passare come db_path)."""
    return str(tmp_path / "test_migration.db")


@pytest.fixture
def populated_db(memory_db):
    """Database con dati di test pre-inseriti (file, canali, tag)."""
    db = memory_db

    # Inserisci canali
    db.insert_or_update_channel(-1001111111111, "Canale Test 1")
    db.insert_or_update_channel(-1002222222222, "Canale Test 2")

    # Inserisci tag
    db.add_tag("lavoro", sort_order=0)
    db.add_tag("personale", sort_order=1)
    db.add_tag("progetti", sort_order=2)

    # Inserisci file
    db.insert_file(
        message_id=1001, filename="documento_lavoro.pdf", size=1024000,
        mime_type="application/pdf", tags="lavoro",
        channel_id=-1001111111111, original_filename="report_q1.pdf"
    )
    db.insert_file(
        message_id=1002, filename="foto_vacanze.jpg", size=2048000,
        mime_type="image/jpeg", tags="personale",
        channel_id=-1001111111111, original_filename="spiaggia.jpg"
    )
    db.insert_file(
        message_id=1003, filename="progetto_xlsx.xlsx", size=512000,
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        tags="progetti", channel_id=-1002222222222, original_filename="budget.xlsx"
    )
    db.insert_file(
        message_id=1004, filename="senza_tag.txt", size=100,
        mime_type="text/plain", tags="",
        channel_id=-1002222222222, original_filename=""
    )

    return db


# ─── Mock Telegram Client ──────────────────────────────────────────────

class MockTelegramClient(QObject):
    """Mock del TelegramClientThread con tutti i segnali necessari."""

    connected = pyqtSignal(bool, str)
    file_list_ready = pyqtSignal(list)
    upload_progress = pyqtSignal(str, int, int)
    upload_done = pyqtSignal(str, bool, str)
    download_progress = pyqtSignal(str, int, int)
    download_done = pyqtSignal(str, bool, str)
    file_deleted = pyqtSignal(bool, str)
    otp_required = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    channels_ready = pyqtSignal(list)
    channel_created = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self._running = True
        self._connected_state = False

    def is_connected(self):
        return self._running and self._connected_state

    def set_connected(self, state: bool = True):
        self._connected_state = state

    def start(self):
        self._running = True

    def stop(self):
        self._running = False

    def wait(self, timeout=5000):
        pass

    def set_phone(self, phone: str):
        pass

    def set_otp(self, code: str):
        pass

    def set_channel(self, channel_id: int):
        pass

    def list_files(self, channel: int):
        pass

    def upload_file(self, channel: int, file_path: str, caption: str = "", op_id: str = ""):
        pass

    def download_file(self, channel: int, message_id: int, output_dir: str,
                      op_id: str = "", output_filename: str = ""):
        pass

    def delete_file(self, channel: int, message_id: int):
        pass

    def list_channels(self):
        pass

    def create_channel(self, title: str, about: str = ""):
        pass


@pytest.fixture
def mock_tg_client():
    """Mock del TelegramClientThread con segnali pronti."""
    return MockTelegramClient()


# ─── Config temporanea ──────────────────────────────────────────────────

@pytest.fixture
def temp_config(tmp_path):
    """Config con percorsi isolati in tmp_path."""
    config = DEFAULT_CONFIG.copy()
    config["download_dir"] = str(tmp_path / "downloads")
    config["api_id"] = "12345"
    config["api_hash"] = "abc123def456"
    config["phone"] = "+391234567890"
    config["channel_id"] = "-1001111111111"
    config["channel_name"] = "Test Channel"
    return config


# ─── QApplication per test Qt ──────────────────────────────────────────

@pytest.fixture(scope="session")
def qapp():
    """QApplication condivisa per tutti i test Qt (creata una sola volta)."""
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app
    # Non chiamiamo app.quit() per non rompere altri test


# ─── Helpers ────────────────────────────────────────────────────────────

@pytest.fixture
def memory_db_isolated(tmp_path):
    """Database SQLite in-memory 'condiviso' tramite URI.
    
    Usa file::memory:?cache=shared per condividere lo stesso
    database in-memory tra connessioni multiple.
    Richiede che il modulo sqlite3 sia compilato con URI support.
    """
    db = Database(db_path="file::memory:?cache=shared")
    yield db
    db.clear_all()


@pytest.fixture
def sample_file_records():
    """Fixture per FileRecord di esempio (senza DB)."""
    from database import FileRecord
    return [
        FileRecord(
            id=1, message_id=1001, filename="doc.pdf", size=1024000,
            mime_type="application/pdf", upload_date="2026-06-01T10:00:00",
            tags="lavoro", local_path=None, telegram_path=None,
            channel_id=-1001111111111, original_filename="report.pdf"
        ),
        FileRecord(
            id=2, message_id=1002, filename="foto.jpg", size=2048000,
            mime_type="image/jpeg", upload_date="2026-06-02T11:00:00",
            tags="personale", local_path="/tmp/foto.jpg", telegram_path=None,
            channel_id=-1001111111111, original_filename="vacanza.jpg"
        ),
        FileRecord(
            id=3, message_id=1003, filename="dati.xlsx", size=512000,
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            upload_date="2026-06-03T12:00:00", tags="",
            local_path=None, telegram_path=None,
            channel_id=-1002222222222, original_filename=""
        ),
    ]


@pytest.fixture
def channel_names():
    """Fixture per la mappa channel_id → channel_name."""
    return {
        -1001111111111: "Canale Test 1",
        -1002222222222: "Canale Test 2",
    }
