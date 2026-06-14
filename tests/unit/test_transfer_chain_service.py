"""
Test per TransferChainService — catena download→upload→(delete) persistente.
"""

from pathlib import Path

import pytest
from PyQt6.QtCore import QObject, pyqtSignal

from database import Database, ChainRecord
from gui.services.transfer_chain_service import TransferChainService


# ─── Fake TransferManager ───────────────────────────────────────────────

class FakeTransferManager(QObject):
    """Fake TransferManager con segnali pilotabili."""

    op_added = pyqtSignal(object)
    op_progress = pyqtSignal(str, int, int, float)
    op_done = pyqtSignal(str, str, bool, str, str)

    def __init__(self):
        super().__init__()
        self._upload_count = 0
        self._download_count = 0
        self._uploads: list = []  # (channel_id, file_path)
        self._downloads: list = []  # (channel_id, message_id, filename, download_dir, original_filename)

    def add_upload(self, channel_id: int, file_path: str) -> str:
        self._upload_count += 1
        op_id = f"upload-{self._upload_count}"
        self._uploads.append((channel_id, file_path))
        return op_id

    def add_download(self, channel_id: int, message_id: int, filename: str,
                     output_dir: str, original_filename: str = "") -> str:
        self._download_count += 1
        op_id = f"download-{self._download_count}"
        self._downloads.append((channel_id, message_id, filename, output_dir, original_filename))
        return op_id

    def emit_op_done(self, op_id: str, op_type: str, success: bool, msg: str, filename: str = ""):
        """Pilota il segnale op_done."""
        self.op_done.emit(op_id, op_type, success, msg, filename or msg)


# ─── Fake TelegramClient ────────────────────────────────────────────────

class FakeTgClient(QObject):
    """Fake TelegramClient che registra le chiamate delete_file."""

    def __init__(self):
        super().__init__()
        self.deletes: list = []  # (channel_id, message_id)

    def delete_file(self, channel_id: int, message_id: int):
        self.deletes.append((channel_id, message_id))

    def is_connected(self):
        return True


# ─── Fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def fake_tm():
    return FakeTransferManager()


@pytest.fixture
def fake_tg():
    return FakeTgClient()


@pytest.fixture
def chain_db(tmp_path):
    """Database con tabella transfer_chains."""
    db_path = tmp_path / "test_chain.db"
    return Database(db_path=str(db_path))


@pytest.fixture
def service(chain_db, fake_tm, fake_tg):
    """TransferChainService con fakes iniettati."""
    return TransferChainService(chain_db, fake_tm, fake_tg)


@pytest.fixture
def sample_files():
    """Lista di file per start_chain."""
    return [
        {
            'message_id': 1001,
            'filename': 'doc.pdf',
            'original_filename': 'report_q1.pdf',
            'channel_id': -1001111111111,
        },
        {
            'message_id': 1002,
            'filename': 'foto.jpg',
            'original_filename': 'vacanza.jpg',
            'channel_id': -1001111111111,
        },
    ]


# ─── Test init ──────────────────────────────────────────────────────────

class TestServiceInit:
    """Test inizializzazione TransferChainService."""

    def test_creates_with_valid_args(self, chain_db, fake_tm, fake_tg):
        """Il servizio si crea senza errori."""
        svc = TransferChainService(chain_db, fake_tm, fake_tg)
        assert svc.db is chain_db
        assert svc.tm is fake_tm
        assert svc.tg is fake_tg

    def test_connects_to_op_done_signal(self, chain_db, fake_tm, fake_tg):
        """Il servizio si connette al segnale op_done del TransferManager."""
        svc = TransferChainService(chain_db, fake_tm, fake_tg)
        # Verifica indiretta: emettendo un segnale non si generano errori
        fake_tm.op_done.emit("test", "upload", True, "/tmp/ok.txt", "ok.txt")
        assert True  # Nessuna eccezione


# ─── Test start_chain ───────────────────────────────────────────────────

class TestStartChain:
    """Test dell'API start_chain."""

    def test_creates_db_rows(self, service, chain_db, sample_files, fake_tm):
        """start_chain inserisce una riga per ogni file nel DB."""
        service.start_chain(sample_files, dest_channel=-1002222222222,
                            is_move=False, download_dir='/tmp/down')

        chains = chain_db.get_chains_by_status(['downloading'])
        assert len(chains) == 2

    def test_downloading_status_with_op_id(self, service, chain_db, sample_files, fake_tm):
        """Le catene hanno status 'downloading' e download_op_id popolato."""
        service.start_chain(sample_files, dest_channel=-1002222222222,
                            is_move=False, download_dir='/tmp/down')

        chains = chain_db.get_chains_by_status(['downloading'])
        for chain in chains:
            assert chain.status == 'downloading'
            assert chain.download_op_id != ''
            assert chain.download_op_id.startswith('download-')

    def test_correct_fields_stored(self, service, chain_db, sample_files, fake_tm):
        """I campi della catena sono corretti nel DB."""
        service.start_chain(sample_files, dest_channel=-1002222222222,
                            is_move=True, download_dir='/tmp/down')

        chains = chain_db.get_chains_by_status(['downloading'])
        chains_by_msg = {c.message_id: c for c in chains}

        assert 1001 in chains_by_msg
        c1 = chains_by_msg[1001]
        assert c1.source_channel == -1001111111111
        assert c1.dest_channel == -1002222222222
        assert c1.filename == 'doc.pdf'
        assert c1.original_name == 'report_q1.pdf'
        assert c1.is_move is True

    def test_copy_sets_is_move_false(self, service, chain_db, sample_files, fake_tm):
        """Copy imposta is_move=False nel DB."""
        service.start_chain(sample_files, dest_channel=-1002222222222,
                            is_move=False, download_dir='/tmp/down')

        chains = chain_db.get_chains_by_status(['downloading'])
        for chain in chains:
            assert chain.is_move is False

    def test_download_dir_passed_to_transfer_manager(self, service, fake_tm, sample_files):
        """La download_dir viene passata correttamente al transfer_manager."""
        service.start_chain(sample_files, dest_channel=-1002222222222,
                            is_move=False, download_dir='/custom/dir')

        assert len(fake_tm._downloads) == 2
        for _, _, _, out_dir, _ in fake_tm._downloads:
            assert out_dir == '/custom/dir'

    def test_original_filename_passed_down(self, service, fake_tm, sample_files):
        """L'original_filename viene passato al transfer_manager."""
        service.start_chain(sample_files, dest_channel=-1002222222222,
                            is_move=False, download_dir='/tmp')

        originals = {fn: orig for _, _, fn, _, orig in fake_tm._downloads}
        assert originals.get('doc.pdf') == 'report_q1.pdf'
        assert originals.get('foto.jpg') == 'vacanza.jpg'

    def test_emits_chain_progress(self, service, fake_tm, sample_files, qtbot):
        """start_chain emette chain_progress per ogni catena."""
        signals = []
        service.chain_progress.connect(lambda cid, st: signals.append((cid, st)))

        service.start_chain(sample_files, dest_channel=-1002222222222,
                            is_move=False, download_dir='/tmp')

        assert len(signals) == 2
        for _, status in signals:
            assert status == 'downloading'

    def test_unique_chain_ids(self, service, chain_db, sample_files, fake_tm):
        """Ogni catena ha un chain_id univoco (8 caratteri)."""
        service.start_chain(sample_files, dest_channel=-1002222222222,
                            is_move=False, download_dir='/tmp')

        chains = chain_db.get_chains_by_status(['downloading'])
        ids = {c.chain_id for c in chains}
        assert len(ids) == 2
        for cid in ids:
            assert len(cid) == 8

    def test_empty_files_list_noop(self, service, chain_db, fake_tm):
        """Lista file vuota non crea catene."""
        service.start_chain([], dest_channel=-1002222222222, is_move=False, download_dir='/tmp')
        chains = chain_db.get_chains_by_status(['pending', 'downloading'])
        assert len(chains) == 0


# ─── Test flusso copy ────────────────────────────────────────────────────

class TestCopyFlow:
    """Test del flusso completo copy: download→upload→done."""

    @pytest.fixture
    def one_file(self):
        return [{'message_id': 1001, 'filename': 'doc.pdf',
                 'original_filename': 'report.pdf', 'channel_id': -1001111111111}]

    def test_full_copy_flow(self, service, chain_db, fake_tm, fake_tg, one_file):
        """Flusso completo copy: download ok → upload ok → done."""
        service.start_chain(one_file, dest_channel=-1002222222222,
                            is_move=False, download_dir='/tmp')

        # Step 1: download done
        chains = chain_db.get_chains_by_status(['downloading'])
        assert len(chains) == 1
        chain = chains[0]
        fake_tm.emit_op_done(chain.download_op_id, 'download', True,
                             '/tmp/report.pdf', 'report.pdf')

        # Verifica: status passato a 'uploading'
        chain = chain_db.get_chain(chain.chain_id)
        assert chain.status == 'uploading'
        assert chain.upload_op_id != ''
        assert chain.temp_file_path == '/tmp/report.pdf'

        # Step 2: upload done
        fake_tm.emit_op_done(chain.upload_op_id, 'upload', True,
                             '/tmp/report.pdf', 'report.pdf')

        # Verifica: status passato a 'done'
        chain = chain_db.get_chain(chain.chain_id)
        assert chain.status == 'done'

        # Nessun delete per copy
        assert len(fake_tg.deletes) == 0

        # chain_done emesso con success=True
        signals = []
        service.chain_done.connect(lambda cid, ok, fn, err: signals.append((cid, ok, fn, err)))
        fake_tm.emit_op_done(f"download-{fake_tm._download_count + 1}", 'download', True,
                             '/tmp/another.pdf', 'another.pdf')
        # (il segnale per questo test specifico è già stato emesso prima del connect)

    def test_copy_does_not_delete_source(self, service, chain_db, fake_tm, fake_tg, one_file):
        """Copy NON cancella il file sorgente dopo upload."""
        service.start_chain(one_file, dest_channel=-1002222222222,
                            is_move=False, download_dir='/tmp')

        chain = chain_db.get_chains_by_status(['downloading'])[0]
        fake_tm.emit_op_done(chain.download_op_id, 'download', True,
                             '/tmp/report.pdf', 'report.pdf')
        chain = chain_db.get_chain(chain.chain_id)
        fake_tm.emit_op_done(chain.upload_op_id, 'upload', True,
                             '/tmp/report.pdf', 'report.pdf')

        assert len(fake_tg.deletes) == 0

    def test_chain_done_signal_on_copy_success(self, service, chain_db, fake_tm, qtbot, one_file):
        """chain_done viene emesso con success=True dopo copy completato."""
        service.start_chain(one_file, dest_channel=-1002222222222,
                            is_move=False, download_dir='/tmp')

        chain = chain_db.get_chains_by_status(['downloading'])[0]

        done_signals = []
        service.chain_done.connect(lambda cid, ok, fn, err: done_signals.append((ok, fn, err)))

        fake_tm.emit_op_done(chain.download_op_id, 'download', True,
                             '/tmp/report.pdf', 'report.pdf')
        chain = chain_db.get_chain(chain.chain_id)
        fake_tm.emit_op_done(chain.upload_op_id, 'upload', True,
                             '/tmp/report.pdf', 'report.pdf')

        assert len(done_signals) == 1
        ok, fn, err = done_signals[0]
        assert ok is True
        assert fn == 'report.pdf'
        assert err == ''

    def test_chain_progress_emitted(self, service, chain_db, fake_tm, qtbot, one_file):
        """chain_progress viene emesso per ogni transizione di stato."""
        service.start_chain(one_file, dest_channel=-1002222222222,
                            is_move=False, download_dir='/tmp')

        chain = chain_db.get_chains_by_status(['downloading'])[0]

        progress_signals = []
        service.chain_progress.connect(lambda cid, st: progress_signals.append((cid, st)))

        # download done → uploading
        fake_tm.emit_op_done(chain.download_op_id, 'download', True,
                             '/tmp/report.pdf', 'report.pdf')

        assert len(progress_signals) >= 1  # Minimal: quello di uploading
        statuses = [st for _, st in progress_signals]
        assert 'uploading' in statuses


# ─── Test flusso move ────────────────────────────────────────────────────

class TestMoveFlow:
    """Test del flusso completo move: download→upload→delete source→done."""

    @pytest.fixture
    def one_file(self):
        return [{'message_id': 1001, 'filename': 'doc.pdf',
                 'original_filename': 'report.pdf', 'channel_id': -1001111111111}]

    def test_full_move_flow(self, service, chain_db, fake_tm, fake_tg, one_file):
        """Flusso completo move: download ok → upload ok → delete source → done."""
        service.start_chain(one_file, dest_channel=-1002222222222,
                            is_move=True, download_dir='/tmp')

        chain = chain_db.get_chains_by_status(['downloading'])[0]
        # Download
        fake_tm.emit_op_done(chain.download_op_id, 'download', True,
                             '/tmp/report.pdf', 'report.pdf')
        chain = chain_db.get_chain(chain.chain_id)
        # Upload
        fake_tm.emit_op_done(chain.upload_op_id, 'upload', True,
                             '/tmp/report.pdf', 'report.pdf')

        # Verifica delete chiamato
        assert len(fake_tg.deletes) == 1
        assert fake_tg.deletes[0] == (-1001111111111, 1001)

        # Verifica status done
        chain = chain_db.get_chain(chain.chain_id)
        assert chain.status == 'done'

    def test_move_deletes_from_source_channel(self, service, chain_db, fake_tm, fake_tg, one_file):
        """Move cancella il file dal canale sorgente (non destinazione)."""
        service.start_chain(one_file, dest_channel=-1002222222222,
                            is_move=True, download_dir='/tmp')

        chain = chain_db.get_chains_by_status(['downloading'])[0]
        fake_tm.emit_op_done(chain.download_op_id, 'download', True,
                             '/tmp/report.pdf', 'report.pdf')
        chain = chain_db.get_chain(chain.chain_id)
        fake_tm.emit_op_done(chain.upload_op_id, 'upload', True,
                             '/tmp/report.pdf', 'report.pdf')

        assert fake_tg.deletes == [(-1001111111111, 1001)]

    def test_move_chain_done_signal(self, service, chain_db, fake_tm, qtbot, one_file):
        """Move completato emette chain_done con success=True."""
        service.start_chain(one_file, dest_channel=-1002222222222,
                            is_move=True, download_dir='/tmp')

        chain = chain_db.get_chains_by_status(['downloading'])[0]

        done_signals = []
        service.chain_done.connect(lambda cid, ok, fn, err: done_signals.append((ok, fn, err)))

        fake_tm.emit_op_done(chain.download_op_id, 'download', True,
                             '/tmp/report.pdf', 'report.pdf')
        chain = chain_db.get_chain(chain.chain_id)
        fake_tm.emit_op_done(chain.upload_op_id, 'upload', True,
                             '/tmp/report.pdf', 'report.pdf')

        assert len(done_signals) == 1
        assert done_signals[0][0] is True


# ─── Test fallimenti ──────────────────────────────────────────────────────

class TestFailures:
    """Test gestione fallimenti download e upload."""

    @pytest.fixture
    def one_file(self):
        return [{'message_id': 1001, 'filename': 'doc.pdf',
                 'original_filename': 'report.pdf', 'channel_id': -1001111111111}]

    def test_download_failure_marks_failed(self, service, chain_db, fake_tm, one_file):
        """Download fallito → status 'failed' con error_msg."""
        service.start_chain(one_file, dest_channel=-1002222222222,
                            is_move=False, download_dir='/tmp')

        chain = chain_db.get_chains_by_status(['downloading'])[0]
        fake_tm.emit_op_done(chain.download_op_id, 'download', False,
                             'File non trovato sul server', 'report.pdf')

        chain = chain_db.get_chain(chain.chain_id)
        assert chain.status == 'failed'
        assert 'File non trovato' in chain.error_msg

    def test_download_failure_emits_chain_done_false(self, service, chain_db, fake_tm, qtbot, one_file):
        """Download fallito emette chain_done con success=False."""
        service.start_chain(one_file, dest_channel=-1002222222222,
                            is_move=False, download_dir='/tmp')

        chain = chain_db.get_chains_by_status(['downloading'])[0]

        done_signals = []
        service.chain_done.connect(lambda cid, ok, fn, err: done_signals.append((ok, fn, err)))

        fake_tm.emit_op_done(chain.download_op_id, 'download', False,
                             'Errore download', 'report.pdf')

        assert len(done_signals) == 1
        ok, fn, err = done_signals[0]
        assert ok is False
        assert fn == 'report.pdf'
        assert 'Errore download' in err

    def test_upload_failure_marks_failed(self, service, chain_db, fake_tm, one_file):
        """Upload fallito → status 'failed' con error_msg."""
        service.start_chain(one_file, dest_channel=-1002222222222,
                            is_move=False, download_dir='/tmp')

        chain = chain_db.get_chains_by_status(['downloading'])[0]
        # Download OK
        fake_tm.emit_op_done(chain.download_op_id, 'download', True,
                             '/tmp/report.pdf', 'report.pdf')
        chain = chain_db.get_chain(chain.chain_id)
        # Upload FAIL
        fake_tm.emit_op_done(chain.upload_op_id, 'upload', False,
                             'Timeout upload', 'report.pdf')

        chain = chain_db.get_chain(chain.chain_id)
        assert chain.status == 'failed'
        assert 'Timeout upload' in chain.error_msg

    def test_upload_failure_emits_chain_done_false(self, service, chain_db, fake_tm, qtbot, one_file):
        """Upload fallito emette chain_done con success=False."""
        service.start_chain(one_file, dest_channel=-1002222222222,
                            is_move=False, download_dir='/tmp')

        chain = chain_db.get_chains_by_status(['downloading'])[0]
        fake_tm.emit_op_done(chain.download_op_id, 'download', True,
                             '/tmp/report.pdf', 'report.pdf')
        chain = chain_db.get_chain(chain.chain_id)

        done_signals = []
        service.chain_done.connect(lambda cid, ok, fn, err: done_signals.append((ok, fn, err)))

        fake_tm.emit_op_done(chain.upload_op_id, 'upload', False,
                             'Errore upload', 'report.pdf')

        assert len(done_signals) == 1
        assert done_signals[0][0] is False


# ─── Test cleanup orfani ──────────────────────────────────────────────────

class TestCleanupOrphaned:
    """Test cleanup_orphaned_files."""

    def test_marks_interrupted_as_failed(self, service, chain_db, fake_tm, sample_files):
        """Catene in pending/downloading/uploading/deleting vengono marcate failed."""
        service.start_chain(sample_files, dest_channel=-1002222222222,
                            is_move=False, download_dir='/tmp')

        # Simula interruzione prima del completamento
        chains_before = chain_db.get_chains_by_status(
            ['pending', 'downloading', 'uploading', 'deleting']
        )
        assert len(chains_before) >= 1  # Almeno le due in downloading

        service.cleanup_orphaned_files()

        # Tutte marcate failed
        for chain_before in chains_before:
            chain = chain_db.get_chain(chain_before.chain_id)
            assert chain.status == 'failed'
            assert 'App interrotta' in chain.error_msg

    def test_does_not_touch_completed(self, service, chain_db, fake_tm, sample_files):
        """Catene già done/failed non vengono modificate."""
        service.start_chain(sample_files, dest_channel=-1002222222222,
                            is_move=False, download_dir='/tmp')

        # Completane una
        chains = chain_db.get_chains_by_status(['downloading'])
        chain = chains[0]
        fake_tm.emit_op_done(chain.download_op_id, 'download', True,
                             '/tmp/test.pdf', 'test.pdf')
        chain = chain_db.get_chain(chain.chain_id)
        fake_tm.emit_op_done(chain.upload_op_id, 'upload', True,
                             '/tmp/test.pdf', 'test.pdf')

        assert chain_db.get_chain(chain.chain_id).status == 'done'

        # Cleanup: la catena 'done' rimane 'done'
        service.cleanup_orphaned_files()
        assert chain_db.get_chain(chain.chain_id).status == 'done'

    def test_emits_chain_done_for_orphans(self, service, chain_db, fake_tm, qtbot, sample_files):
        """cleanup emette chain_done per ogni catena orfana."""
        service.start_chain(sample_files, dest_channel=-1002222222222,
                            is_move=False, download_dir='/tmp')

        done_signals = []
        service.chain_done.connect(lambda cid, ok, fn, err: done_signals.append((ok, fn, err)))

        service.cleanup_orphaned_files()

        # 2 catene in downloading → 2 segnali
        assert len(done_signals) == 2
        for ok, fn, err in done_signals:
            assert ok is False
            assert 'App interrotta' in err

    def test_cleans_temp_files(self, service, chain_db, fake_tm, sample_files, tmp_path):
        """I file temporanei segnati nel DB vengono cancellati."""
        temp_file = tmp_path / "orphan_temp.dat"
        temp_file.write_text("temp data")

        # Crea una catena con temp_file_path
        service.start_chain(sample_files[:1], dest_channel=-1002222222222,
                            is_move=False, download_dir='/tmp')
        chain = chain_db.get_chains_by_status(['downloading'])[0]
        chain_db.update_chain_status(chain.chain_id, 'downloading',
                                     temp_file_path=str(temp_file))

        assert temp_file.exists()

        service.cleanup_orphaned_files()

        assert not temp_file.exists()


# ─── Test segnali da operazioni non-catena ──────────────────────────────

class TestNonChainOps:
    """Test che operazioni non di catena siano ignorate correttamente."""

    def test_single_upload_ignored(self, service, chain_db, fake_tm):
        """Upload non associato a una catena non causa effetti collaterali."""
        fake_tm.emit_op_done("random-op-id", "upload", True, "/tmp/file.txt", "file.txt")
        # Nessuna eccezione, nessuna modifica al DB catene
        assert chain_db.get_chains_by_status(['pending', 'downloading', 'uploading',
                                               'deleting', 'done', 'failed']) == []

    def test_single_download_ignored(self, service, chain_db, fake_tm):
        """Download non associato a una catena non causa effetti collaterali."""
        fake_tm.emit_op_done("random-op-id", "download", True, "/tmp/file.txt", "file.txt")
        assert chain_db.get_chains_by_status(['pending', 'downloading', 'uploading',
                                               'deleting', 'done', 'failed']) == []

    def test_empty_op_id_ignored(self, service, fake_tm):
        """op_id vuoto non causa errori (get_chain_by_*_op ritorna None)."""
        fake_tm.op_done.emit("", "download", True, "/tmp/file.txt", "file.txt")
        assert True  # Nessuna eccezione


# ─── Test DB CRUD per transfer_chains ─────────────────────────────────

class TestChainDbCrud:
    """Test dei metodi CRUD per transfer_chains in database.py."""

    def test_insert_chain(self, chain_db):
        """insert_chain inserisce una riga con status 'pending'."""
        chain_db.insert_chain(
            chain_id="abc12345", source_channel=-1001, dest_channel=-1002,
            message_id=500, filename="test.pdf", original_name="report.pdf",
            is_move=False
        )
        chain = chain_db.get_chain("abc12345")
        assert chain is not None
        assert chain.status == 'pending'
        assert chain.filename == 'test.pdf'
        assert chain.original_name == 'report.pdf'
        assert chain.is_move is False

    def test_insert_chain_move(self, chain_db):
        """is_move=True viene salvato correttamente."""
        chain_db.insert_chain(
            chain_id="move1", source_channel=-1001, dest_channel=-1002,
            message_id=501, filename="move_me.pdf", is_move=True
        )
        chain = chain_db.get_chain("move1")
        assert chain.is_move is True

    def test_insert_chain_defaults(self, chain_db):
        """Valori di default per original_name e is_move."""
        chain_db.insert_chain(
            chain_id="def1", source_channel=-1001, dest_channel=-1002,
            message_id=502, filename="defaults.txt"
        )
        chain = chain_db.get_chain("def1")
        assert chain.original_name == ''
        assert chain.is_move is False
        assert chain.error_msg == ''

    def test_update_chain_status(self, chain_db):
        """update_chain_status modifica status e campi opzionali."""
        chain_db.insert_chain(
            chain_id="upd1", source_channel=-1001, dest_channel=-1002,
            message_id=503, filename="update_me.pdf"
        )
        chain_db.update_chain_status("upd1", "downloading",
                                     download_op_id="dl-123",
                                     temp_file_path="/tmp/downloaded.pdf")
        chain = chain_db.get_chain("upd1")
        assert chain.status == 'downloading'
        assert chain.download_op_id == 'dl-123'
        assert chain.temp_file_path == '/tmp/downloaded.pdf'

    def test_update_chain_status_ignores_unknown_keys(self, chain_db):
        """update_chain_status ignora chiavi non permesse."""
        chain_db.insert_chain(
            chain_id="upd2", source_channel=-1001, dest_channel=-1002,
            message_id=504, filename="safe.pdf"
        )
        # 'hacker_key' dovrebbe essere ignorata senza errori
        chain_db.update_chain_status("upd2", "done", hacker_key="evil")
        chain = chain_db.get_chain("upd2")
        assert chain.status == 'done'

    def test_get_chain_nonexistent(self, chain_db):
        """get_chain restituisce None per ID inesistente."""
        assert chain_db.get_chain("non-esisto") is None

    def test_get_chain_by_download_op(self, chain_db):
        """get_chain_by_download_op trova la catena per op_id."""
        chain_db.insert_chain(
            chain_id="bydl1", source_channel=-1001, dest_channel=-1002,
            message_id=505, filename="find_me.pdf"
        )
        chain_db.update_chain_status("bydl1", "downloading", download_op_id="dl-xyz")
        chain = chain_db.get_chain_by_download_op("dl-xyz")
        assert chain is not None
        assert chain.chain_id == "bydl1"

    def test_get_chain_by_download_op_empty(self, chain_db):
        """get_chain_by_download_op con stringa vuota restituisce None."""
        assert chain_db.get_chain_by_download_op("") is None

    def test_get_chain_by_upload_op(self, chain_db):
        """get_chain_by_upload_op trova la catena per op_id."""
        chain_db.insert_chain(
            chain_id="byul1", source_channel=-1001, dest_channel=-1002,
            message_id=506, filename="upload_find.pdf"
        )
        chain_db.update_chain_status("byul1", "uploading", upload_op_id="ul-abc")
        chain = chain_db.get_chain_by_upload_op("ul-abc")
        assert chain is not None
        assert chain.chain_id == "byul1"

    def test_get_chain_by_upload_op_empty(self, chain_db):
        """get_chain_by_upload_op con stringa vuota restituisce None."""
        assert chain_db.get_chain_by_upload_op("") is None

    def test_get_chains_by_status_multiple(self, chain_db):
        """get_chains_by_status restituisce catene con status multipli."""
        chain_db.insert_chain(
            chain_id="s1", source_channel=-1001, dest_channel=-1002,
            message_id=507, filename="a.pdf"
        )
        chain_db.insert_chain(
            chain_id="s2", source_channel=-1001, dest_channel=-1002,
            message_id=508, filename="b.pdf"
        )
        chain_db.update_chain_status("s1", "done")
        chain_db.update_chain_status("s2", "failed", error_msg="test error")

        result = chain_db.get_chains_by_status(["done", "failed"])
        assert len(result) == 2
        ids = {c.chain_id for c in result}
        assert ids == {"s1", "s2"}

    def test_get_chains_by_status_empty_list(self, chain_db):
        """Lista status vuota restituisce lista vuota."""
        assert chain_db.get_chains_by_status([]) == []


# ─── Test temp file cleanup ─────────────────────────────────────────────

class TestTempFileCleanup:
    """Test della pulizia dei file temporanei."""

    @pytest.fixture
    def one_file(self):
        return [{'message_id': 1001, 'filename': 'doc.pdf',
                 'original_filename': 'report.pdf', 'channel_id': -1001111111111}]

    def test_temp_file_cleaned_after_success(self, service, chain_db, fake_tm, one_file, tmp_path):
        """Il file temporaneo viene cancellato dopo upload riuscito."""
        temp_file = tmp_path / "success_temp.dat"
        temp_file.write_text("test data")

        service.start_chain(one_file, dest_channel=-1002222222222,
                            is_move=False, download_dir='/tmp')
        chain = chain_db.get_chains_by_status(['downloading'])[0]
        fake_tm.emit_op_done(chain.download_op_id, 'download', True,
                             str(temp_file), 'report.pdf')
        chain = chain_db.get_chain(chain.chain_id)
        fake_tm.emit_op_done(chain.upload_op_id, 'upload', True,
                             str(temp_file), 'report.pdf')

        assert not temp_file.exists()

    def test_temp_file_cleaned_after_failure(self, service, chain_db, fake_tm, one_file, tmp_path):
        """Il file temporaneo viene cancellato anche dopo upload fallito."""
        temp_file = tmp_path / "fail_temp.dat"
        temp_file.write_text("test data")

        service.start_chain(one_file, dest_channel=-1002222222222,
                            is_move=False, download_dir='/tmp')
        chain = chain_db.get_chains_by_status(['downloading'])[0]
        fake_tm.emit_op_done(chain.download_op_id, 'download', True,
                             str(temp_file), 'report.pdf')
        chain = chain_db.get_chain(chain.chain_id)
        fake_tm.emit_op_done(chain.upload_op_id, 'upload', False,
                             str(temp_file), 'report.pdf')

        assert not temp_file.exists()
