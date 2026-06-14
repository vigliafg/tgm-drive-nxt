# TransferChainService — Progetto Dettagliato

> Refactoring della catena copy/move da stato volatile in RAM a stato persistente in SQLite.
> **Obiettivo**: eliminare `_pending_copy_ops` e `_suppress_deleted_refresh` da `main_window.py`,
> rendere la catena resilienti ai crash e testabile senza GUI.

---

## 1. Stato attuale (cosa esiste oggi)

### 1.1 Codice in `main_window.py` da rimuovere

```python
# Riga ~110 — attributi
self._pending_copy_ops: dict = {}          # op_id → {dest, source, message_id, is_move, original_filename}
self._suppress_deleted_refresh: set = set() # memory leak potenziale

# Righe ~530-565 — _start_copy_move_operation
#   Crea TransferOp di download, popola _pending_copy_ops[op_id] = {...}

# Righe ~440-510 — _on_transfer_done
#   if op_id in self._pending_copy_ops:
#       if download & success → upload verso dest
#       if upload & success → pulisci temp, if move → delete source, refresh
#       if !success → notifica errore, pulisci temp
#   return  ← NON chiama _refresh_cloud per le catene

# Righe ~415-435 — _on_file_deleted
#   if msg_id in self._suppress_deleted_refresh → skip refresh ← questo se ne va
```

### 1.2 Flusso attuale (fragile)

```
_start_copy_move_operation()
  └→ per ogni file:
       transfer_manager.add_download(source, msg_id, ...)  → op_id
       _pending_copy_ops[op_id] = {dest, source, message_id, is_move}

_on_transfer_done(op_id, "download", success, local_path, ...)
  └→ if op_id in _pending_copy_ops:
       if success:
         info = _pending_copy_ops.pop(op_id)
         new_op_id = transfer_manager.add_upload(info.dest, local_path)
         _pending_copy_ops[new_op_id] = info

_on_transfer_done(new_op_id, "upload", success, uploaded_path, ...)
  └→ if op_id in _pending_copy_ops:
       info = _pending_copy_ops.pop(new_op_id)
       Path(uploaded_path).unlink(missing_ok=True)
       if info.is_move:
         _suppress_deleted_refresh.add(info.message_id)
         tg_client.delete_file(info.source, info.message_id)
       _refresh_channel_db(info.dest)

_on_file_deleted(success, msg_id)
  └→ if msg_id in _suppress_deleted_refresh:
       _suppress_deleted_refresh.discard(msg_id)
       return  # ← salta refresh perché già fatto dal dest handler
```

**Problemi**: 3 callback, 2 dict, 1 set, stato perso al crash, intestabile.

---

## 2. Nuova architettura

### 2.1 Nuovi file

```
gui/
├── services/
│   ├── __init__.py
│   └── transfer_chain_service.py   ← NUOVO (~90 righe)

tests/
└── unit/
    └── test_transfer_chain_service.py  ← NUOVO (~80 test)
```

### 2.2 Tabella SQLite in `database.py`

```sql
CREATE TABLE IF NOT EXISTS transfer_chains (
    chain_id        TEXT PRIMARY KEY,          -- UUID4 (8 char)
    source_channel  INTEGER NOT NULL,
    dest_channel    INTEGER NOT NULL,
    message_id      INTEGER NOT NULL,
    filename        TEXT NOT NULL,
    original_name   TEXT DEFAULT '',
    is_move         INTEGER DEFAULT 0,         -- 0=copy, 1=move
    status          TEXT DEFAULT 'pending',     -- pending|downloading|uploading|deleting|done|failed
    download_op_id  TEXT DEFAULT '',
    upload_op_id    TEXT DEFAULT '',
    temp_file_path  TEXT DEFAULT '',
    error_msg       TEXT DEFAULT '',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chain_status ON transfer_chains(status);
CREATE INDEX IF NOT EXISTS idx_chain_download_op ON transfer_chains(download_op_id);
CREATE INDEX IF NOT EXISTS idx_chain_upload_op ON transfer_chains(upload_op_id);
```

### 2.3 Dataclass

```python
@dataclass
class ChainRecord:
    chain_id: str
    source_channel: int
    dest_channel: int
    message_id: int
    filename: str
    original_name: str
    is_move: bool          # convertito da int
    status: str
    download_op_id: str
    upload_op_id: str
    temp_file_path: str
    error_msg: str
    created_at: str
    updated_at: str
```

### 2.4 Metodi aggiuntivi in `database.py`

```python
# database.py — nuovi metodi

def insert_chain(self, chain_id, source_channel, dest_channel, message_id,
                 filename, original_name, is_move) -> None:
    """Inserisce una nuova catena con status='pending'."""

def update_chain_status(self, chain_id, status, **kwargs) -> None:
    """Aggiorna status e campi opzionali (download_op_id, upload_op_id, temp_file_path, error_msg)."""

def get_chain(self, chain_id) -> Optional[ChainRecord]:
    """Recupera una catena per ID."""

def get_chain_by_download_op(self, op_id) -> Optional[ChainRecord]:
    """Recupera la catena associata a un'operazione di download."""

def get_chain_by_upload_op(self, op_id) -> Optional[ChainRecord]:
    """Recupera la catena associata a un'operazione di upload."""

def get_chains_by_status(self, statuses: list) -> List[ChainRecord]:
    """Recupera tutte le catene con i dati status specificati."""
```

### 2.5 `TransferChainService` — la classe

```python
# gui/services/transfer_chain_service.py

from PyQt6.QtCore import QObject, pyqtSignal
from database import Database
from transfer_manager import TransferManager
from telegram_client import TelegramClientThread
from pathlib import Path
import uuid

class TransferChainService(QObject):
    """Gestisce la catena download→upload→(delete) per copy/move tra canali.

    Ogni catena è persistita in SQLite. Sopravvive ai crash.
    I segnali arrivano dal TransferManager, non dalla MainWindow.
    """

    # ── Segnali ──────────────────────────────────────────────────
    chain_progress = pyqtSignal(str, str)        # chain_id, status
    chain_done = pyqtSignal(str, bool, str, str)  # chain_id, success, filename, error_msg
    all_chains_complete = pyqtSignal(int)         # numero catene completate

    def __init__(self, db: Database, transfer_manager: TransferManager,
                 tg_client: TelegramClientThread):
        super().__init__()
        self.db = db
        self.tm = transfer_manager
        self.tg = tg_client

        # Connessione ai segnali del TransferManager
        self.tm.op_done.connect(self._on_op_done)

    # ── API pubblica ─────────────────────────────────────────────

    def start_chain(self, files: list, dest_channel: int, is_move: bool,
                    download_dir: str):
        """Avvia una catena per ogni file nella lista.

        files: lista di dict {message_id, filename, original_filename, channel_id}
        """
        for f in files:
            chain_id = str(uuid.uuid4())[:8]
            source_ch = f.get('channel_id', 0)
            display_name = f.get('original_filename') or f['filename']
            download_op_id = self.tm.add_download(
                source_ch, f['message_id'], f['filename'],
                download_dir, f.get('original_filename', '')
            )
            self.db.insert_chain(
                chain_id=chain_id,
                source_channel=source_ch,
                dest_channel=dest_channel,
                message_id=f['message_id'],
                filename=f['filename'],
                original_name=f.get('original_filename', ''),
                is_move=is_move,
            )
            self.db.update_chain_status(chain_id, 'downloading',
                                        download_op_id=download_op_id)
            self.chain_progress.emit(chain_id, 'downloading')

    def cleanup_orphaned_files(self):
        """Ripulisce i file temporanei di catene interrotte. Chiamato all'avvio."""
        orphaned = self.db.get_chains_by_status(
            ['pending', 'downloading', 'uploading']
        )
        for chain in orphaned:
            if chain.temp_file_path:
                Path(chain.temp_file_path).unlink(missing_ok=True)
            self.db.update_chain_status(chain.chain_id, 'failed',
                                        error_msg='App interrotta durante trasferimento')
            self.chain_done.emit(chain.chain_id, False, chain.original_name or chain.filename,
                                'App interrotta durante trasferimento')

    # ── Gestione segnali dal TransferManager ─────────────────────

    def _on_op_done(self, op_id: str, op_type: str, success: bool,
                    msg: str, filename: str):
        """Smista il segnale in base al tipo di operazione e al contesto."""
        if op_type == 'download':
            chain = self.db.get_chain_by_download_op(op_id)
            if chain:
                self._handle_download_done(chain, success, msg)
                return
        elif op_type == 'upload':
            chain = self.db.get_chain_by_upload_op(op_id)
            if chain:
                self._handle_upload_done(chain, success, msg)
                return
        # Se non è una catena, non facciamo nulla (è un upload/download singolo)

    def _handle_download_done(self, chain, success: bool, local_path: str):
        if not success:
            self.db.update_chain_status(chain.chain_id, 'failed',
                                        error_msg=local_path)
            self.chain_done.emit(chain.chain_id, False,
                                 chain.original_name or chain.filename, local_path)
            return

        # Download ok → avvia upload verso il canale di destinazione
        upload_op_id = self.tm.add_upload(chain.dest_channel, local_path)
        self.db.update_chain_status(chain.chain_id, 'uploading',
                                     upload_op_id=upload_op_id,
                                     temp_file_path=local_path)
        self.chain_progress.emit(chain.chain_id, 'uploading')

    def _handle_upload_done(self, chain, success: bool, uploaded_path: str):
        # Pulisci sempre il file temporaneo
        Path(uploaded_path).unlink(missing_ok=True)
        # Pulisci anche il temp_file_path salvato (potrebbe differire)
        if chain.temp_file_path:
            Path(chain.temp_file_path).unlink(missing_ok=True)

        if not success:
            self.db.update_chain_status(chain.chain_id, 'failed',
                                        error_msg=uploaded_path)
            self.chain_done.emit(chain.chain_id, False,
                                 chain.original_name or chain.filename, uploaded_path)
            return

        # Upload ok
        if chain.is_move:
            # Avvia delete sul canale sorgente
            self.tg.delete_file(chain.source_channel, chain.message_id)
            self.db.update_chain_status(chain.chain_id, 'deleting')
            # Il delete è fire-and-forget: il file_deleted è gestito da
            # MainWindow._on_file_deleted per aggiornare la UI

        self.db.update_chain_status(chain.chain_id, 'done')
        self.chain_done.emit(chain.chain_id, True,
                             chain.original_name or chain.filename, '')
```
**(~90 righe)**

---

## 3. Modifiche a `main_window.py`

### 3.1 Cosa si aggiunge

```python
# In __init__, dopo self.transfer_manager:
from gui.services.transfer_chain_service import TransferChainService
self.chain_service = TransferChainService(self.db, self.transfer_manager, self.tg_client)
self.chain_service.chain_done.connect(self._on_chain_done)
self.chain_service.chain_progress.connect(self._on_chain_progress)

# Chiamata all'avvio
self.chain_service.cleanup_orphaned_files()
```

### 3.2 Cosa si rimuove

```python
# ELIMINARE:
self._pending_copy_ops: dict = {}
self._suppress_deleted_refresh: set = set()

# ELIMINARE da _start_copy_move_operation:
self._pending_copy_ops[op_id] = {...}  # ~riga 562

# ELIMINARE da _on_transfer_done:
#   tutto il blocco if op_id in self._pending_copy_ops: (~40 righe)

# ELIMINARE da _on_file_deleted:
#   if int(msg_id) in self._suppress_deleted_refresh: (~3 righe)
```

### 3.3 Cosa si modifica

```python
def _start_copy_move_operation(self, is_move: bool):
    # ...validazione files, dialog destinazione...
    # INVECE DI:
    #   for file in files:
    #       op_id = self.transfer_manager.add_download(...)
    #       self._pending_copy_ops[op_id] = {...}
    # USA:
    files_data = [
        {
            'message_id': file.message_id,
            'filename': file.filename,
            'original_filename': file.original_filename,
            'channel_id': file.channel_id if file.channel_id else self.channel_id,
        }
        for file in files
    ]
    self.chain_service.start_chain(
        files_data, dest_channel_id, is_move, str(self.download_dir)
    )

def _on_transfer_done(self, op_id, op_type, success, msg, filename):
    self.cloud_model.remove_transfer(op_id)

    # SOLO gestione upload/download singoli (non catene)
    if success:
        self._notify_transfer_done(op_type, filename)
    if success and op_type == 'upload':
        self._refresh_cloud()
    if success:
        self._refresh_local_tree()

def _on_chain_done(self, chain_id, success, filename, error_msg):
    """Chiamato quando UNA catena completa (successo o fallimento)."""
    if success:
        self._notify_transfer_done('upload', filename)
        self._refresh_cloud()
    else:
        short_error = error_msg[:120] if error_msg else 'errore sconosciuto'
        self.status_bar.showMessage(f"❌ Copia/Sposta fallito: {filename} — {short_error}")

def _on_chain_progress(self, chain_id, status):
    """Opzionale: aggiorna la status bar con lo stato corrente."""
    pass  # Per ora silent, si può arricchire dopo

def _on_file_deleted(self, success, msg_id):
    if success:
        self.db.delete_file(int(msg_id))
        self._refresh_cloud()
    # NIENTE _suppress_deleted_refresh — non serve più
```

---

## 4. Test (`tests/unit/test_transfer_chain_service.py`)

```python
# ~80 test, tutti puri (zero GUI)

class TestTransferChainService:
    # Fixture: memory_db + FakeTransferManager + FakeTgClient

    def test_start_chain_creates_db_rows(self, service, memory_db):
        """start_chain inserisce una riga per ogni file."""
        files = [{'message_id': 1001, 'filename': 'a.pdf', 'channel_id': -1001}]
        service.start_chain(files, dest_channel=-1002, is_move=False, download_dir='/tmp')
        chains = memory_db.get_chains_by_status(['downloading'])
        assert len(chains) == 1

    def test_chain_flow_copy_success(self, service, fake_tm, memory_db):
        """Flusso completo copy: download→upload→done."""
        # setup
        service.start_chain([{...}], dest=-1002, is_move=False, download_dir='/tmp')
        chain = memory_db.get_chains_by_status(['downloading'])[0]

        # step 1: download done
        fake_tm.emit_op_done(chain.download_op_id, 'download', True, '/tmp/a.pdf', 'a.pdf')
        chain = memory_db.get_chain(chain.chain_id)
        assert chain.status == 'uploading'

        # step 2: upload done
        fake_tm.emit_op_done(chain.upload_op_id, 'upload', True, '/tmp/a.pdf', 'a.pdf')
        chain = memory_db.get_chain(chain.chain_id)
        assert chain.status == 'done'

    def test_chain_flow_move_success(self, service, fake_tm, memory_db, fake_tg):
        """Flusso completo move: download→upload→delete source."""
        ...

    def test_chain_download_failure(self, service, fake_tm, memory_db):
        """Download fallito → status 'failed', chain_done emesso."""
        ...

    def test_chain_upload_failure(self, service, fake_tm, memory_db):
        """Upload fallito → status 'failed', temp file pulito."""
        ...

    def test_cleanup_orphaned_files(self, service, memory_db, tmp_path):
        """Catene interrotte vengono marcate 'failed' con error_msg."""
        ...

    def test_chain_done_signal(self, service, qtbot):
        """Il segnale chain_done viene emesso con i parametri corretti."""
        ...

    def test_single_upload_ignored(self, service, fake_tm):
        """Upload non di catena viene ignorato dal service."""
        ...

    def test_temp_file_cleanup_on_success(self, ...):
        """Il file temporaneo viene cancellato dopo upload riuscito."""
        ...

    def test_temp_file_cleanup_on_failure(self, ...):
        """Il file temporaneo viene cancellato anche dopo upload fallito."""
        ...
```

---

## 5. Sequenza di implementazione

| Step | File | Azione | Tempo |
|---|---|---|---|
| **A** | `database.py` | Aggiungere tabella `transfer_chains` in `_init_db`, dataclass `ChainRecord`, 6 metodi CRUD | 10 min |
| **B** | `gui/services/__init__.py` | File vuoto | 1 min |
| **C** | `gui/services/transfer_chain_service.py` | Classe `TransferChainService` (~90 righe) | 15 min |
| **D** | `main_window.py` | Aggiungere `chain_service`, `_on_chain_done`, `_on_chain_progress`; rimuovere `_pending_copy_ops`, `_suppress_deleted_refresh`; modificare `_start_copy_move_operation`, `_on_transfer_done`, `_on_file_deleted` | 30 min |
| **E** | `tests/unit/test_transfer_chain_service.py` | Test del servizio (~80 test) | 20 min |
| **F** | `pytest tests/` | Verifica 337 test esistenti + nuovi passano | 5 min |
| **G** | `code-reviewer-deepseek` | Review delle modifiche | in parallelo |

**Tempo totale stimato: ~1 ora e 20 minuti**

---

## 6. Riepilogo impatto

| Metrica | Prima | Dopo |
|---|---|---|
| Stato catena | 2 dict in RAM | SQLite (sopravvive ai crash) |
| `main_window.py` | 773 stmts | ~730 stmts (-43) |
| File temporanei orfani al crash | ✅ rimangono | ❌ puliti all'avvio |
| Memory leak `_suppress_deleted_refresh` | 🔴 possibile | 🟢 eliminato |
| Testabilità catena | 🔴 0% | 🟢 100% |
| `_on_transfer_done` | ~60 righe | ~15 righe |
| Nuovo codice testabile | 0 | 90 righe (`TransferChainService`) + 80 test |
