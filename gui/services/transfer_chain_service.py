"""TransferChainService — catena persistente download→upload→(delete) per copy/move.

Ogni catena è salvata in SQLite (tabella `transfer_chains`). Sopravvive ai crash.
I segnali arrivano dal TransferManager, non dalla MainWindow.
"""

from PyQt6.QtCore import QObject, pyqtSignal
from database import Database
from gui.transfer_manager import TransferManager
from telegram_client import TelegramClientThread
from pathlib import Path
import uuid


class TransferChainService(QObject):
    """Gestisce la catena download→upload→(delete) per copy/move tra canali.

    Ogni catena è persistita in SQLite. Sopravvive ai crash.
    I segnali arrivano dal TransferManager, non dalla MainWindow.
    """

    # ── Segnali ──────────────────────────────────────────────────
    chain_progress = pyqtSignal(str, str)          # chain_id, status
    chain_done = pyqtSignal(str, bool, str, str)   # chain_id, success, filename, error_msg

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
            ['pending', 'downloading', 'uploading', 'deleting']
        )
        for chain in orphaned:
            if chain.temp_file_path:
                Path(chain.temp_file_path).unlink(missing_ok=True)
            self.db.update_chain_status(chain.chain_id, 'failed',
                                        error_msg='App interrotta durante trasferimento')
            self.chain_done.emit(chain.chain_id, False,
                                 chain.original_name or chain.filename,
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
        # Se non è una catena, non facciamo nulla (upload/download singolo)

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
            self.db.update_chain_status(chain.chain_id, 'done')
        else:
            self.db.update_chain_status(chain.chain_id, 'done')

        self.chain_done.emit(chain.chain_id, True,
                             chain.original_name or chain.filename, '')
