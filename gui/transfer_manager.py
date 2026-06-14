from PyQt6.QtCore import QObject, pyqtSignal
from typing import List, Optional, Dict
from dataclasses import dataclass, field
from pathlib import Path
import uuid
import time


@dataclass
class TransferOp:
    op_id: str
    op_type: str  # "upload" or "download"
    channel_id: int
    file_path: str = ""
    message_id: int = 0
    filename: str = ""
    original_filename: str = ""
    status: str = "queued"  # queued, running, done, error
    progress: int = 0
    total: int = 0
    error_msg: str = ""
    meta: dict = field(default_factory=dict)


class TransferManager(QObject):
    op_added = pyqtSignal(object)  # TransferOp
    op_progress = pyqtSignal(str, int, int, float)  # op_id, current, total, speed_mb_s
    op_done = pyqtSignal(str, str, bool, str, str)  # op_id, op_type, success, msg, filename
    queue_changed = pyqtSignal()

    def __init__(self, tg_client):
        super().__init__()
        self.tg_client = tg_client
        self._queue: List[TransferOp] = []
        self._current: Optional[TransferOp] = None
        self._running = False
        self._last_progress_time: Dict[str, float] = {}
        self._last_progress_bytes: Dict[str, int] = {}

        # Connect Telegram client signals
        self.tg_client.upload_progress.connect(self._on_upload_progress)
        self.tg_client.upload_done.connect(self._on_upload_done)
        self.tg_client.download_progress.connect(self._on_download_progress)
        self.tg_client.download_done.connect(self._on_download_done)

    def add_upload(self, channel_id: int, file_path: str) -> str:
        op_id = str(uuid.uuid4())[:8]
        op = TransferOp(
            op_id=op_id,
            op_type="upload",
            channel_id=channel_id,
            file_path=file_path,
            filename=Path(file_path).name,
        )
        self._queue.append(op)
        self.op_added.emit(op)
        self.queue_changed.emit()
        if not self._running:
            self._process_next()
        return op_id

    def add_download(self, channel_id: int, message_id: int, filename: str, output_dir: str, original_filename: str = "") -> str:
        op_id = str(uuid.uuid4())[:8]
        out_path = Path(output_dir) / (original_filename or filename)
        op = TransferOp(
            op_id=op_id,
            op_type="download",
            channel_id=channel_id,
            message_id=message_id,
            file_path=str(out_path),
            filename=filename,
            original_filename=original_filename,
        )
        self._queue.append(op)
        self.op_added.emit(op)
        self.queue_changed.emit()
        if not self._running:
            self._process_next()
        return op_id

    def _process_next(self):
        while self._queue:
            if not self.tg_client.is_connected():
                self._current = self._queue.pop(0)
                self._current.status = "error"
                self._current.error_msg = "Client non connesso"
                self.op_done.emit(self._current.op_id, self._current.op_type, False, "Client non connesso", self._current.filename)
                continue
            self._running = True
            self._current = self._queue.pop(0)
            self._current.status = "running"
            self.queue_changed.emit()

            if self._current.op_type == "upload":
                self.tg_client.upload_file(
                    self._current.channel_id,
                    self._current.file_path,
                    op_id=self._current.op_id,
                )
            else:
                self.tg_client.download_file(
                    self._current.channel_id,
                    self._current.message_id,
                    str(Path(self._current.file_path).parent),
                    op_id=self._current.op_id,
                    output_filename=self._current.original_filename or self._current.filename,
                )
            return
        self._running = False
        self._current = None

    def _calc_speed(self, op_id: str, current: int) -> float:
        now = time.time()
        last_time = self._last_progress_time.get(op_id, now)
        last_bytes = self._last_progress_bytes.get(op_id, current)
        delta_time = now - last_time
        delta_bytes = current - last_bytes
        speed = (delta_bytes / delta_time) / (1024 * 1024) if delta_time > 0 else 0.0
        self._last_progress_time[op_id] = now
        self._last_progress_bytes[op_id] = current
        return speed

    def _on_upload_progress(self, op_id: str, current: int, total: int):
        if self._current and self._current.op_id == op_id:
            self._current.progress = current
            self._current.total = total
            speed = self._calc_speed(op_id, current)
            self.op_progress.emit(op_id, current, total, speed)

    def _on_upload_done(self, op_id: str, success: bool, msg: str):
        self._last_progress_time.pop(op_id, None)
        self._last_progress_bytes.pop(op_id, None)
        if self._current and self._current.op_id == op_id:
            self._current.status = "done" if success else "error"
            self._current.error_msg = msg if not success else ""
            display_name = self._current.original_filename or self._current.filename
            self.op_done.emit(op_id, self._current.op_type, success, msg, display_name)
            self._process_next()

    def _on_download_progress(self, op_id: str, current: int, total: int):
        if self._current and self._current.op_id == op_id:
            self._current.progress = current
            self._current.total = total
            speed = self._calc_speed(op_id, current)
            self.op_progress.emit(op_id, current, total, speed)

    def _on_download_done(self, op_id: str, success: bool, msg: str):
        self._last_progress_time.pop(op_id, None)
        self._last_progress_bytes.pop(op_id, None)
        if self._current and self._current.op_id == op_id:
            self._current.status = "done" if success else "error"
            self._current.error_msg = msg if not success else ""
            display_name = self._current.original_filename or self._current.filename
            self.op_done.emit(op_id, self._current.op_type, success, msg, display_name)
            self._process_next()

    def get_queue(self) -> List[TransferOp]:
        return self._queue.copy()

    def get_current(self) -> Optional[TransferOp]:
        return self._current
