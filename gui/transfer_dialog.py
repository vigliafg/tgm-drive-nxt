from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QScrollArea, QWidget, QFrame, QCheckBox
)
from PyQt6.QtCore import Qt
from pathlib import Path
from gui.transfer_manager import TransferManager, TransferOp


class TransferItem(QWidget):
    def __init__(self, op: TransferOp, parent=None):
        super().__init__(parent)
        self.op_id = op.op_id
        self.op_type = op.op_type
        self.filename = op.filename
        self.ch_info = f" (ID: {op.channel_id})" if op.channel_id else ""
        self.total_bytes = 0
        self._file_size_mb = 0.0
        if op.op_type == "upload" and Path(op.file_path).exists():
            self._file_size_mb = Path(op.file_path).stat().st_size / (1024 * 1024)
        self._build_ui(op)

    def _build_ui(self, op: TransferOp):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        icon = "⬆" if op.op_type == "upload" else "⬇"
        self.icon_lbl = QLabel(icon)
        if op.op_type == "upload":
            self.icon_lbl.setStyleSheet(
                "font-size: 16px; color: white; background-color: #1976D2; border-radius: 4px; padding: 4px;"
            )
        else:
            self.icon_lbl.setStyleSheet(
                "font-size: 16px; color: white; background-color: #FF8F00; border-radius: 4px; padding: 4px;"
            )
        self.icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_lbl.setMinimumWidth(32)
        layout.addWidget(self.icon_lbl)

        self.progress = QProgressBar()
        self.progress.setMaximum(100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress.setFormat(f"{self.filename}{self.ch_info}  %p%")
        self.progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #444;
                border-radius: 4px;
                text-align: center;
                font-weight: bold;
                color: #eee;
            }
            QProgressBar::chunk {
                background-color: #2196F3;
                border-radius: 4px;
            }
        """)
        self.progress.setToolTip(f"Canale: {op.channel_id}")
        layout.addWidget(self.progress, stretch=1)

        self.info_lbl = QLabel("In attesa...")
        self.info_lbl.setStyleSheet("color: #888; font-size: 11px; min-width: 140px;")
        layout.addWidget(self.info_lbl)

        self.status_lbl = QLabel("⏳")
        self.status_lbl.setStyleSheet("color: #888; font-size: 12px;")
        layout.addWidget(self.status_lbl)

        if op.status == "running":
            self.status_lbl.setText("⚡")
            self.status_lbl.setStyleSheet("color: #2196F3; font-size: 12px;")
        elif op.status == "done":
            self.mark_done(True, "")
        elif op.status == "error":
            self.mark_done(False, op.error_msg)

    def _format_info(self, speed_mb_s: float, total_mb: float) -> str:
        if total_mb > 0:
            return f"{total_mb:.1f} MB  |  {speed_mb_s:.1f} MB/s"
        return f"{speed_mb_s:.1f} MB/s"

    def set_progress(self, current: int, total: int, speed_mb_s: float = 0.0):
        self.total_bytes = total
        if total > 0:
            self.progress.setMaximum(total)
            self.progress.setValue(current)
            pct = int(current / total * 100)
            self.status_lbl.setText(f"⚡ {pct}%")
            self.status_lbl.setStyleSheet("color: #2196F3; font-size: 12px;")
            self.info_lbl.setText(self._format_info(speed_mb_s, total / (1024 * 1024)))
        else:
            self.status_lbl.setText("⚡")
            self.status_lbl.setStyleSheet("color: #2196F3; font-size: 12px;")
            self.info_lbl.setText(self._format_info(speed_mb_s, 0))

    def mark_done(self, success: bool, msg: str):
        self.progress.setMaximum(100)
        self.progress.setValue(100 if success else 0)
        total_mb = self.total_bytes / (1024 * 1024) if self.total_bytes > 0 else self._file_size_mb
        if success:
            self.progress.setFormat(f"✅ {self.filename}{self.ch_info}")
            self.progress.setStyleSheet("""
                QProgressBar {
                    border: 1px solid #444;
                    border-radius: 4px;
                    text-align: center;
                    font-weight: bold;
                    color: #eee;
                }
                QProgressBar::chunk {
                    background-color: #4CAF50;
                    border-radius: 4px;
                }
            """)
            self.status_lbl.setText("✅")
            self.status_lbl.setStyleSheet("color: #4CAF50; font-size: 12px;")
            self.info_lbl.setText(f"{total_mb:.1f} MB")
            self.icon_lbl.setStyleSheet(
                "font-size: 16px; color: #4CAF50; background-color: #2c2c2c; border-radius: 4px; padding: 4px;"
            )
        else:
            self.progress.setFormat(f"❌ {self.filename}{self.ch_info}")
            self.progress.setStyleSheet("""
                QProgressBar {
                    border: 1px solid #444;
                    border-radius: 4px;
                    text-align: center;
                    font-weight: bold;
                    color: #eee;
                }
                QProgressBar::chunk {
                    background-color: #F44336;
                    border-radius: 4px;
                }
            """)
            self.status_lbl.setText("❌")
            self.status_lbl.setStyleSheet("color: #F44336; font-size: 12px;")
            self.info_lbl.setText("Errore")
            self.progress.setToolTip(msg)
            self.icon_lbl.setStyleSheet(
                "font-size: 16px; color: #F44336; background-color: #2c2c2c; border-radius: 4px; padding: 4px;"
            )


class TransferDialog(QDialog):
    def __init__(self, manager: TransferManager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.items: dict = {}
        self.total_ops = 0
        self.completed_ops = 0
        self.setWindowTitle("Trasferimenti")
        self.setMinimumWidth(550)
        self.setMinimumHeight(350)
        self._build_ui()
        self._connect_signals()
        self._load_existing()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        title = QLabel("📦 Coda di trasferimento")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        self.status_label = QLabel("⏳ Coda vuota")
        self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #888;")
        layout.addWidget(self.status_label)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.container_layout.setSpacing(4)
        self.container_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll, stretch=1)

        btn_layout = QHBoxLayout()
        self.auto_clear_checkbox = QCheckBox("🧹 Pulisci completati automaticamente")
        self.auto_clear_checkbox.setChecked(True)
        btn_layout.addWidget(self.auto_clear_checkbox)
        btn_layout.addStretch()
        self.clear_btn = QPushButton("🧹 Pulisci completati")
        self.clear_btn.clicked.connect(self._clear_completed)
        btn_layout.addWidget(self.clear_btn)
        self.clear_all_btn = QPushButton("🗑 Pulisci lista")
        self.clear_all_btn.clicked.connect(self._clear_all)
        btn_layout.addWidget(self.clear_all_btn)
        layout.addLayout(btn_layout)

    def _connect_signals(self):
        self.manager.op_added.connect(self._on_op_added)
        self.manager.op_progress.connect(self._on_op_progress)
        self.manager.op_done.connect(self._on_op_done)

    def _load_existing(self):
        for op in self.manager.get_queue():
            self._on_op_added(op)
        current = self.manager.get_current()
        if current:
            self._on_op_added(current)

    def _on_op_added(self, op: TransferOp):
        if op.op_id in self.items:
            return
        item = TransferItem(op)
        self.items[op.op_id] = item
        self.container_layout.addWidget(item)
        self.total_ops += 1
        self._update_status()
        if not self.isVisible():
            self.show()

    def _on_op_progress(self, op_id: str, current: int, total: int, speed_mb_s: float):
        item = self.items.get(op_id)
        if item:
            item.set_progress(current, total, speed_mb_s)

    def _on_op_done(self, op_id: str, op_type: str, success: bool, msg: str, filename: str):
        item = self.items.get(op_id)
        if item:
            item.mark_done(success, msg)
            self.completed_ops += 1
            self._update_status()
            if self.auto_clear_checkbox.isChecked():
                self._clear_completed()

    def _clear_completed(self):
        to_remove = []
        for op_id, item in self.items.items():
            txt = item.status_lbl.text()
            if txt.startswith("✅") or txt.startswith("❌"):
                to_remove.append(op_id)
        for op_id in to_remove:
            item = self.items.pop(op_id)
            self.container_layout.removeWidget(item)
            item.deleteLater()
            self.total_ops -= 1
            if self.completed_ops > 0:
                self.completed_ops -= 1
        self._update_status()

    def _clear_all(self):
        to_remove = list(self.items.keys())
        for op_id in to_remove:
            item = self.items.pop(op_id)
            self.container_layout.removeWidget(item)
            item.deleteLater()
        self.total_ops = 0
        self.completed_ops = 0
        self._update_status()

    def _update_status(self):
        if self.total_ops == 0:
            self.status_label.setText("⏳ Coda vuota")
            self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #888;")
        elif self.completed_ops >= self.total_ops:
            self.status_label.setText("✅ Coda completata")
            self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #4CAF50;")
        else:
            self.status_label.setText(f"⏳ {self.completed_ops} di {self.total_ops} completati")
            self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #2196F3;")

    def closeEvent(self, event):
        event.accept()
