import json
import os
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTreeView, QTableView, QPushButton, QLineEdit, QLabel,
    QAbstractItemView, QMessageBox,
    QStatusBar, QToolBar, QGroupBox, QHeaderView, QFileDialog,
    QTextEdit, QComboBox, QApplication, QSystemTrayIcon,
    QMenuBar, QMenu
)
from PyQt6.QtGui import QFileSystemModel, QIcon, QPixmap
from PyQt6.QtCore import Qt, QDir, pyqtSignal, QTimer, QModelIndex
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QKeySequence, QShortcut

from database import Database
from telegram_client import TelegramClientThread
from gui.cloud_model import CloudFileModel, TagDelegate
from gui.transfer_manager import TransferManager
from gui.transfer_dialog import TransferDialog
from gui.destination_dialog import DestinationDialog
from gui.settings_dialog import SettingsDialog
from gui.tag_chip_widget import TagChipWidget
from config import load_config, save_config


class SmartDropArea(QGroupBox):
    files_dropped = pyqtSignal(list)
    cloud_files_dropped = pyqtSignal(list)

    def __init__(self, title="Trascina qui i file da caricare o file dal cloud da scaricare", parent=None):
        super().__init__(title, parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(90)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAutoFillBackground(True)
        self._default_title = title
        self._default_style = "QGroupBox { border: 2px dashed #aaa; border-radius: 8px; padding: 10px; }"
        self.setStyleSheet(self._default_style)
        self._upload_label = "Trascina qui i file da caricare"
        self._download_label = "Trascina qui i file dal cloud da scaricare"
        self._pending_files = []
        self._upload_target_name = "canale selezionato"
        self._download_target_name = "cartella selezionata"

    def set_drop_targets(self, upload_channel_name: str, download_dir_name: str):
        self._upload_target_name = upload_channel_name
        self._download_target_name = download_dir_name

    def _update_title(self, is_upload: bool, count: int = 0, target_name: str = ""):
        if is_upload:
            self.setTitle(f"⬆ Upload di {count} file in {target_name}")
        else:
            self.setTitle(f"⬇ Download di {count} file in {target_name}")

    def dragEnterEvent(self, event: QDragEnterEvent):
        mime = event.mimeData()
        if mime.hasUrls():
            paths = [u.toLocalFile() for u in mime.urls() if os.path.isfile(u.toLocalFile())]
            if paths:
                event.acceptProposedAction()
                self._pending_files = paths
                self.setStyleSheet(
                    "QGroupBox { border: 2px dashed #4CAF50; border-radius: 8px; padding: 10px; background-color: #e8f5e9; } "
                    "QGroupBox::title { color: #1b5e20; background-color: #e8f5e9; }"
                )
                self._update_title(is_upload=True, count=len(paths), target_name=self._upload_target_name)
        elif mime.hasFormat("application/x-tgmdrive-cloud-file"):
            event.acceptProposedAction()
            self.setStyleSheet(
                "QGroupBox { border: 2px dashed #03A9F4; border-radius: 8px; padding: 10px; background-color: #e3f2fd; } "
                "QGroupBox::title { color: #0d47a1; background-color: #e3f2fd; }"
                )
            data = bytes(mime.data("application/x-tgmdrive-cloud-file")).decode()
            files = json.loads(data)
            self._update_title(is_upload=False, count=len(files), target_name=self._download_target_name)

    def dragLeaveEvent(self, event):
        self._pending_files = []
        self.setStyleSheet(self._default_style)
        self.setTitle(self._default_title)

    def dropEvent(self, event: QDropEvent):
        self.setStyleSheet(self._default_style)
        self.setTitle(self._default_title)
        mime = event.mimeData()
        if mime.hasUrls():
            paths = [u.toLocalFile() for u in mime.urls() if os.path.isfile(u.toLocalFile())]
            if paths:
                self.files_dropped.emit(paths)
        elif mime.hasFormat("application/x-tgmdrive-cloud-file"):
            data = bytes(mime.data("application/x-tgmdrive-cloud-file")).decode()
            files = json.loads(data)
            self.cloud_files_dropped.emit(files)


class MainWindow(QMainWindow):
    def __init__(self, tg_client: TelegramClientThread, db: Database, config: dict):
        super().__init__()
        self.tg_client = tg_client
        self.db = db
        self.config = config
        self.channel_id = int(config.get("channel_id", 0)) if config.get("channel_id") else 0
        self.channel_name = config.get("channel_name", "")
        self.download_dir = Path(config.get("download_dir", str(Path.home() / "TGM_Drive_Downloads")))
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self._channel_filter = 0  # 0 = tutti i canali
        self._drop_upload_channel_id = self.channel_id
        self._drop_download_dir = self.download_dir
        self._pending_copy_ops: dict = {}  # op_id → {dest_channel, source_channel, message_id, is_move, original_filename}
        self._suppress_deleted_refresh: set = set()  # message_id di move già refresh-ati dal dest handler
        self._current_tag_filter: str = ""  # "" = nessun filtro (mostra tutti)
        self._pending_tags: dict[str, list[str]] = {}  # filename → [tag1, tag2, ...] (per upload con tag)
        self._tag_delegate = TagDelegate()

        self.transfer_manager = TransferManager(self.tg_client)
        self.transfer_dialog = TransferDialog(self.transfer_manager, self)
        self.transfer_manager.op_added.connect(self._on_transfer_op_added)
        self.transfer_manager.op_done.connect(self._on_transfer_done)

        self.tray_icon = QSystemTrayIcon(self)
        tray_icon = QIcon.fromTheme("document-save")
        if tray_icon.isNull():
            pixmap = QPixmap(32, 32)
            pixmap.fill(Qt.GlobalColor.blue)
            tray_icon = QIcon(pixmap)
        self.tray_icon.setIcon(tray_icon)
        self.tray_icon.setVisible(True)

        self.setWindowTitle("TGM Drive - Cloud Telegram")
        self.setMinimumSize(1200, 700)

        self._build_ui()
        self._connect_signals()
        self._load_channel_names()
        self._load_favorite_channels()
        self._load_tag_list()
        self._refresh_cloud()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # Menu bar
        menubar = QMenuBar()
        file_menu = QMenu("File", self)
        file_menu.addAction("⚙️ Impostazioni", self._on_open_settings)
        menubar.addMenu(file_menu)
        self.setMenuBar(menubar)

        # Toolbar
        toolbar = QToolBar()
        self.btn_upload = QPushButton("⬆ Upload")
        self.btn_download = QPushButton("⬇ Download")
        self.btn_refresh = QPushButton("🔄 Aggiorna")
        self.btn_transfers = QPushButton("📦 Trasferimenti")
        self.btn_create_channel = QPushButton("📢 Seleziona Canale")
        self.btn_select_dir = QPushButton("📂 Cartella Download")
        self.btn_settings = QPushButton("⚙️ Impostazioni")
        self.btn_settings.setToolTip("Apri la finestra delle impostazioni (tema, font, Telegram)")
        self.btn_favorites = QPushButton("⭐ Canali Preferiti")
        self.btn_favorites.setToolTip("Apri la gestione canali preferiti")

        toolbar.addWidget(self.btn_upload)
        toolbar.addWidget(self.btn_download)
        toolbar.addSeparator()
        toolbar.addWidget(self.btn_transfers)
        toolbar.addWidget(self.btn_refresh)
        toolbar.addWidget(self.btn_create_channel)
        toolbar.addWidget(self.btn_select_dir)
        toolbar.addSeparator()
        toolbar.addWidget(self.btn_favorites)
        toolbar.addWidget(self.btn_settings)
        self.addToolBar(toolbar)

        # Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Local explorer
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_label = QLabel("📁 File System Locale")
        left_label.setStyleSheet("font-weight: bold; padding: 4px;")
        left_layout.addWidget(left_label)

        self.fs_model = QFileSystemModel()
        self.fs_model.setRootPath(QDir.homePath())
        self.local_tree = QTreeView()
        self.local_tree.setModel(self.fs_model)
        self.local_tree.setRootIndex(self.fs_model.index(QDir.homePath()))
        self.local_tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.local_tree.setDragEnabled(True)
        self.local_tree.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.local_tree.setColumnWidth(0, 250)
        left_layout.addWidget(self.local_tree)

        # Smart Drop area with controls
        drop_controls = QHBoxLayout()
        self.drop_channel_combo = QComboBox()
        self.drop_channel_combo.setMinimumWidth(200)
        self.drop_channel_combo.setToolTip("Canale di upload per il drop box")
        drop_controls.addWidget(QLabel("📢 Canale upload:"))
        drop_controls.addWidget(self.drop_channel_combo, stretch=1)

        # Tag combo per upload
        self.drop_tag_combo = QComboBox()
        self.drop_tag_combo.setMinimumWidth(140)
        self.drop_tag_combo.setToolTip("Tag da assegnare ai file uploadati via drop")
        self.drop_tag_combo.addItem("🏷️ Nessun tag", "")
        drop_controls.addWidget(QLabel("Tag:"))
        drop_controls.addWidget(self.drop_tag_combo)

        self.drop_dir_btn = QPushButton("📂 Cartella download")
        self.drop_dir_btn.setToolTip("Scegli la cartella di download per il drop box")
        self.drop_dir_btn.clicked.connect(self._on_drop_select_download_dir)
        drop_controls.addWidget(self.drop_dir_btn)
        left_layout.addLayout(drop_controls)

        self.drop_area = SmartDropArea()
        left_layout.addWidget(self.drop_area)
        splitter.addWidget(left_widget)

        # Right: Cloud explorer
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        # Favorite channels bar
        self.channel_bar = QWidget()
        self.channel_bar_layout = QHBoxLayout(self.channel_bar)
        self.channel_bar_layout.setContentsMargins(4, 4, 4, 4)
        self.channel_bar_layout.setSpacing(6)
        self.channel_bar_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        right_layout.addWidget(self.channel_bar)

        # Filter bar
        filter_layout = QHBoxLayout()
        self.channel_filter_combo = QComboBox()
        self.channel_filter_combo.addItem("📁 Tutti i canali", 0)
        self.channel_filter_combo.currentIndexChanged.connect(self._on_channel_filter_changed)
        filter_layout.addWidget(QLabel("Filtro canale:"))
        filter_layout.addWidget(self.channel_filter_combo, stretch=1)
        right_layout.addLayout(filter_layout)

        # Search bar
        search_layout = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Cerca file per nome (sottostringa)...")
        self.btn_search = QPushButton("Cerca")
        self.btn_clear_search = QPushButton("Reset")
        search_layout.addWidget(self.search_edit, stretch=1)
        search_layout.addWidget(self.btn_search)
        search_layout.addWidget(self.btn_clear_search)
        right_layout.addLayout(search_layout)

        right_label = QLabel("☁️ Cloud Telegram")
        right_label.setStyleSheet("font-weight: bold; padding: 4px;")
        right_layout.addWidget(right_label)

        # Cloud toolbar: azioni specifiche per la sezione cloud
        cloud_toolbar = QHBoxLayout()
        cloud_toolbar.setSpacing(6)

        self.btn_copy_checked = QPushButton("📋 Copia selezionati")
        self.btn_copy_checked.setToolTip("Copia i file selezionati in un altro canale")
        self.btn_copy_checked.setStyleSheet(
            "QPushButton { background-color: #2980b9; color: white; border: none; border-radius: 4px; padding: 4px 10px; }"
            "QPushButton:hover { background-color: #3498db; }"
        )
        self.btn_copy_checked.clicked.connect(self._on_copy_checked)
        cloud_toolbar.addWidget(self.btn_copy_checked)

        self.btn_move_checked = QPushButton("📦 Sposta selezionati")
        self.btn_move_checked.setToolTip("Sposta i file selezionati in un altro canale (elimina dalla sorgente)")
        self.btn_move_checked.setStyleSheet(
            "QPushButton { background-color: #e67e22; color: white; border: none; border-radius: 4px; padding: 4px 10px; }"
            "QPushButton:hover { background-color: #f39c12; }"
        )
        self.btn_move_checked.clicked.connect(self._on_move_checked)
        cloud_toolbar.addWidget(self.btn_move_checked)

        self.btn_delete_checked = QPushButton("☑ Cancella selezionati")
        self.btn_delete_checked.setToolTip("Elimina dal cloud tutti i file con checkbox selezionata")
        self.btn_delete_checked.setStyleSheet(
            "QPushButton { background-color: #c0392b; color: white; border: none; border-radius: 4px; padding: 4px 10px; }"
            "QPushButton:hover { background-color: #e74c3c; }"
        )
        self.btn_delete_checked.clicked.connect(self._on_delete_checked)
        cloud_toolbar.addWidget(self.btn_delete_checked)

        cloud_toolbar.addStretch()
        right_layout.addLayout(cloud_toolbar)

        self.cloud_model = CloudFileModel()
        self.cloud_table = QTableView()
        self.cloud_table.setModel(self.cloud_model)
        self.cloud_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.cloud_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.cloud_table.setAlternatingRowColors(True)
        self.cloud_table.horizontalHeader().setStretchLastSection(True)
        self.cloud_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.cloud_table.setColumnWidth(0, 30)
        self.cloud_table.setColumnWidth(1, 280)
        self.cloud_table.setColumnWidth(2, 100)
        self.cloud_table.setColumnWidth(3, 120)
        self.cloud_table.setColumnWidth(4, 150)
        self.cloud_table.setColumnWidth(5, 150)
        self.cloud_table.setDragEnabled(True)
        self.cloud_table.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.cloud_table.doubleClicked.connect(self._on_cloud_double_click)
        # Tag delegate per colonna Tags
        self.cloud_table.setItemDelegateForColumn(6, self._tag_delegate)
        right_layout.addWidget(self.cloud_table)

        # Tag chip box compatto sotto la cloud table
        self.tag_chip_widget = TagChipWidget()
        self.tag_chip_widget.tag_clicked.connect(self._on_tag_chip_clicked)
        self.tag_chip_widget.manage_requested.connect(self._on_open_tags_settings)
        right_layout.addWidget(self.tag_chip_widget)

        # Info bar sotto la tabella: totale file e selezionati
        self.cloud_info_label = QLabel()
        self.cloud_info_label.setStyleSheet("color: #888; padding: 2px 6px; font-size: 12px;")
        right_layout.addWidget(self.cloud_info_label)

        splitter.addWidget(right_widget)
        splitter.setSizes([400, 800])
        main_layout.addWidget(splitter, stretch=1)

        # Status bar
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Pronto")
        self.setStatusBar(self.status_bar)

        # Shortcuts
        QShortcut(QKeySequence("F5"), self, self._refresh_cloud)
        QShortcut(QKeySequence("Delete"), self, self._on_delete_checked)

    def _connect_signals(self):
        self.btn_upload.clicked.connect(self._on_upload)
        self.btn_download.clicked.connect(self._on_download)
        self.btn_refresh.clicked.connect(self._refresh_cloud)
        self.btn_transfers.clicked.connect(self._show_transfer_dialog)
        self.btn_create_channel.clicked.connect(self._on_create_channel)
        self.btn_select_dir.clicked.connect(self._on_select_download_dir)
        self.btn_settings.clicked.connect(self._on_open_settings)
        self.btn_favorites.clicked.connect(self._on_open_favorites)
        self.btn_search.clicked.connect(self._on_search)
        self.btn_clear_search.clicked.connect(self._on_clear_search)
        self.search_edit.returnPressed.connect(self._on_search)
        self.drop_area.files_dropped.connect(self._on_drop_files_upload)
        self.drop_area.cloud_files_dropped.connect(self._on_drop_cloud_download)
        # Cloud table signals
        self.cloud_table.horizontalHeader().sectionClicked.connect(self._on_header_section_clicked)
        self.cloud_table.clicked.connect(self._on_cloud_clicked)
        self.cloud_model.dataChanged.connect(self._update_cloud_info_label)
        self.cloud_model.modelReset.connect(self._update_cloud_info_label)
        # Tag cell changed
        self.cloud_model.dataChanged.connect(self._on_tag_cell_changed)
        # Telegram client signals
        self.tg_client.file_list_ready.connect(self._on_file_list_ready)
        self.tg_client.file_deleted.connect(self._on_file_deleted)
        self.tg_client.error_occurred.connect(self._on_error)
        self.tg_client.channels_ready.connect(self._on_channels_loaded)



    def _on_cloud_double_click(self, index):
        if index.column() == 6:  # Colonna Tags → modifica inline
            self.cloud_table.edit(index)
            return
        file = self.cloud_model.get_file(index)
        if file and file.message_id > 0:
            ch_id = file.channel_id if file.channel_id else self.channel_id
            self.transfer_manager.add_download(ch_id, file.message_id, file.filename, str(self.download_dir), file.original_filename)
            self.transfer_dialog.show()

    def _on_cloud_clicked(self, index):
        """Toggle manuale della checkbox quando l'utente clicca sulla colonna 0.
        Necessario perché SelectRows in QTableView intercetta il click prima
        che il delegate possa toggle-are la CheckStateRole."""
        if index.column() == self.cloud_model.CHECKBOX_COL:
            current = self.cloud_model.data(index, Qt.ItemDataRole.CheckStateRole)
            if current is not None:
                new_state = Qt.CheckState.Unchecked if current == Qt.CheckState.Checked else Qt.CheckState.Checked
                self.cloud_model.setData(index, new_state, Qt.ItemDataRole.CheckStateRole)

    def _on_upload(self):
        indexes = self.local_tree.selectionModel().selectedRows()
        if not indexes:
            QMessageBox.information(self, "Info", "Seleziona file dall'explorer locale")
            return
        paths = []
        for idx in indexes:
            path = self.fs_model.filePath(idx)
            if os.path.isfile(path):
                paths.append(path)
        if not paths:
            QMessageBox.information(self, "Info", "Nessun file selezionato")
            return
        self._upload_paths(paths)

    def _on_drop_files_upload(self, paths: list):
        ch_id = self._drop_upload_channel_id or self.channel_id
        if not ch_id:
            QMessageBox.warning(self, "Errore", "Configura prima un canale Telegram")
            return
        tag = self.drop_tag_combo.currentData() or ""
        self.status_bar.showMessage(f"Upload di {len(paths)} file in coda...")
        for path in paths:
            self.transfer_manager.add_upload(ch_id, path)
            if tag:
                self._pending_tags.setdefault(Path(path).name, []).append(tag)
        self.transfer_dialog.show()

    def _on_drop_cloud_download(self, files: list):
        out_dir = str(self._drop_download_dir)
        for f in files:
            ch_id = f.get("channel_id") or self.channel_id
            self.transfer_manager.add_download(ch_id, f["message_id"], f["filename"], out_dir, f.get("original_filename", ""))
        if files:
            self.transfer_dialog.show()

    def _upload_paths(self, paths: list):
        if not self.channel_id:
            QMessageBox.warning(self, "Errore", "Configura prima un canale Telegram")
            return
        tag = self.drop_tag_combo.currentData() or ""
        self.status_bar.showMessage(f"Upload di {len(paths)} file in coda...")
        for path in paths:
            self.transfer_manager.add_upload(self.channel_id, path)
            if tag:
                self._pending_tags.setdefault(Path(path).name, []).append(tag)
        self.transfer_dialog.show()

    def _on_download(self):
        indexes = self.cloud_table.selectionModel().selectedRows()
        if not indexes:
            QMessageBox.information(self, "Info", "Seleziona un file dal cloud")
            return
        # Estrai i file selezionati prima di modificare il modello
        # (add_download aggiunge transfer rows al cloud_model, spostando gli indici)
        files = []
        for idx in indexes:
            file = self.cloud_model.get_file(idx)
            if file and file.message_id > 0:
                files.append(file)
        for file in files:
            ch_id = file.channel_id if file.channel_id else self.channel_id
            self.transfer_manager.add_download(ch_id, file.message_id, file.filename, str(self.download_dir), file.original_filename)
        self.transfer_dialog.show()

    def _on_delete_checked(self):
        """Elimina tutti i file con checkbox selezionata."""
        files = self.cloud_model.get_checked_files()
        if not files:
            QMessageBox.information(self, "Info", "Nessun file selezionato. Usa le checkbox a sinistra per selezionare i file da eliminare.")
            return
        reply = QMessageBox.question(
            self, "Conferma", f"Eliminare {len(files)} file selezionati dal cloud?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        for file in files:
            ch_id = file.channel_id if file.channel_id else self.channel_id
            self.tg_client.delete_file(ch_id, file.message_id)

    def _on_copy_checked(self):
        """Copia i file selezionati in un altro canale."""
        self._start_copy_move_operation(is_move=False)

    def _on_move_checked(self):
        """Sposta i file selezionati in un altro canale (elimina dalla sorgente)."""
        self._start_copy_move_operation(is_move=True)

    def _start_copy_move_operation(self, is_move: bool):
        """Avvia l'operazione di copia o sposta: dialog destinazione → download → upload."""
        files = self.cloud_model.get_checked_files()
        if not files:
            QMessageBox.information(
                self, "Info",
                "Nessun file selezionato. Usa le checkbox a sinistra per selezionare i file."
            )
            return

        # Raccogli gli ID dei canali sorgente da escludere
        source_ids = {f.channel_id if f.channel_id else self.channel_id for f in files}

        action = "move" if is_move else "copy"
        dialog = DestinationDialog(
            self.db, self, action=action, exclude_channel_ids=source_ids
        )
        if not dialog.exec():
            return

        dest_channel_id = dialog.selected_channel_id
        self.status_bar.showMessage(
            f"{'Spostamento' if is_move else 'Copia'} di {len(files)} file in corso..."
        )

        for file in files:
            source_ch = file.channel_id if file.channel_id else self.channel_id
            display_name = file.original_filename or file.filename
            op_id = self.transfer_manager.add_download(
                source_ch, file.message_id, file.filename,
                str(self.download_dir), file.original_filename
            )
            # Marca il download come operazione intermedia: non mostrare nella tabella
            self._pending_copy_ops[op_id] = {
                'dest_channel': dest_channel_id,
                'source_channel': source_ch,
                'message_id': file.message_id,
                'is_move': is_move,
                'original_filename': display_name,
            }

        self.transfer_dialog.show()

    def _on_header_section_clicked(self, logical_index: int):
        """Toggle tutte le checkbox quando si clicca sull'header della colonna 0."""
        if logical_index == self.cloud_model.CHECKBOX_COL:
            self.cloud_model.toggle_all()

    def _on_file_deleted(self, success, msg_id):
        if success:
            self.db.delete_file(int(msg_id))
            # Salta il refresh se già gestito dal move handler (dest == current)
            if int(msg_id) in self._suppress_deleted_refresh:
                self._suppress_deleted_refresh.discard(int(msg_id))
                return
            self._refresh_cloud()
        else:
            # Pulisci il set anche in caso di fallimento per evitare leak
            self._suppress_deleted_refresh.discard(int(msg_id))

    def _refresh_cloud(self):
        if not self.channel_id:
            self.status_bar.showMessage("Nessun canale configurato")
            return
        self.status_bar.showMessage("Caricamento lista file dal cloud...")
        self.tg_client.list_files(self.channel_id)

    def _refresh_channel_db(self, channel_id: int):
        """Aggiorna il DB con i file di uno specifico canale, poi refresh la vista.
        Usa un handler one-shot e disconnette temporaneamente _on_file_list_ready."""
        # Disconnetti il gestore principale per evitare doppia elaborazione
        try:
            self.tg_client.file_list_ready.disconnect(self._on_file_list_ready)
        except TypeError:
            pass

        def _one_shot(files):
            # Disconnetti questo handler one-shot
            try:
                self.tg_client.file_list_ready.disconnect(_one_shot)
            except TypeError:
                pass
            # Inserisci i file nel DB con il channel_id corretto
            for f in files:
                caption = f.get("caption", "")
                original_filename = self._extract_original_filename(caption, f["filename"])
                self.db.insert_file(
                    message_id=f["message_id"],
                    filename=f["filename"],
                    size=f.get("size", 0),
                    mime_type=f.get("mime_type", ""),
                    tags="",
                    channel_id=channel_id,
                    original_filename=original_filename,
                )
            # Refresh la vista se il filtro è cross-channel o il canale matcha
            if channel_id == self.channel_id or self._channel_filter in (0, -1):
                self._refresh_file_list()
            # Riconnetti il gestore principale
            self.tg_client.file_list_ready.connect(self._on_file_list_ready)

        self.tg_client.file_list_ready.connect(_one_shot)
        self.tg_client.list_files(channel_id)

    def _on_file_list_ready(self, files: list):
        for f in files:
            caption = f.get("caption", "")
            original_filename = self._extract_original_filename(caption, f["filename"])
            # Applica tag pendente se presente
            tag_list = self._pending_tags.get(f["filename"], [])
            pending_tag = tag_list.pop(0) if tag_list else ""
            if not tag_list:
                self._pending_tags.pop(f["filename"], None)
            self.db.insert_file(
                message_id=f["message_id"],
                filename=f["filename"],
                size=f.get("size", 0),
                mime_type=f.get("mime_type", ""),
                tags="",
                channel_id=self.channel_id,
                original_filename=original_filename,
            )
            if pending_tag:
                self.db.update_file_tag(f["message_id"], pending_tag)
        self._refresh_file_list()

    def _extract_original_filename(self, caption: str, telegram_filename: str) -> str:
        """Estrae il nome file originale dalla caption del messaggio Telegram.
        Se la caption termina con un'estensione valida (.ext),
        la usa come original_filename. Altrimenti restituisce stringa vuota."""
        import re
        if not caption or not caption.strip():
            return ""
        caption = caption.strip()
        # Deve assomigliare a un nome file: no newline/slash/backslash,
        # e terminare con .estensione (1-6 caratteri alfanumerici)
        if '\n' in caption or '/' in caption or '\\' in caption:
            return ""
        if re.search(r'\.[a-zA-Z0-9]{1,6}$', caption):
            return caption
        return ""

    def _refresh_local_tree(self):
        # Salva i percorsi delle directory attualmente espanse
        expanded_paths = []
        def collect_expanded(parent=QModelIndex()):
            for i in range(self.fs_model.rowCount(parent)):
                idx = self.fs_model.index(i, 0, parent)
                if self.local_tree.isExpanded(idx):
                    path = self.fs_model.filePath(idx)
                    expanded_paths.append(path)
                    collect_expanded(idx)
        collect_expanded()

        # Rigenera il QFileSystemModel per forzare il reload dei dati dal disco
        current_root = self.fs_model.rootPath()
        self.local_tree.setModel(None)
        self.fs_model = QFileSystemModel()
        self.fs_model.setRootPath(current_root)
        self.local_tree.setModel(self.fs_model)
        self.local_tree.setRootIndex(self.fs_model.index(current_root))
        self.local_tree.setColumnWidth(0, 250)
        self.local_tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

        # Ripristina lo stato di espansione usando directoryLoaded + retry
        pending = set(os.path.normpath(p) for p in expanded_paths)
        if pending:
            def on_loaded(path=None):
                # Prova a espandere tutti i pending ancora non validi
                for pending_path in list(pending):
                    idx = self.fs_model.index(pending_path)
                    if idx.isValid():
                        self.local_tree.expand(idx)
                        pending.discard(pending_path)
                if not pending:
                    try:
                        self.fs_model.directoryLoaded.disconnect(on_loaded)
                    except TypeError:
                        pass
            self.fs_model.directoryLoaded.connect(on_loaded)
            # Tentativo immediato
            QTimer.singleShot(0, lambda: on_loaded(""))
            # Fallback: disconnetti dopo 3 secondi
            def _disconnect():
                try:
                    self.fs_model.directoryLoaded.disconnect(on_loaded)
                except TypeError:
                    pass
            QTimer.singleShot(3000, _disconnect)

    def _refresh_file_list(self):
        records = self.db.get_all_files(self._channel_filter)
        self.cloud_model.set_files(records)
        self._update_cloud_info_label()
        self.status_bar.showMessage(f"{len(records)} file nel cloud")

    def _update_cloud_info_label(self):
        """Aggiorna il label sotto la tabella e il pulsante cancella con i conteggi."""
        total = self.cloud_model.file_count()
        checked = self.cloud_model.checked_count()
        if checked > 0:
            self.cloud_info_label.setText(f"{total} file — {checked} selezionati")
            self.btn_copy_checked.setText(f"📋 Copia {checked} selezionati")
            self.btn_move_checked.setText(f"📦 Sposta {checked} selezionati")
            self.btn_delete_checked.setText(f"☑ Cancella {checked} selezionati")
        else:
            self.cloud_info_label.setText(f"{total} file")
            self.btn_copy_checked.setText("📋 Copia selezionati")
            self.btn_move_checked.setText("📦 Sposta selezionati")
            self.btn_delete_checked.setText("☑ Cancella selezionati")

    def _on_search(self):
        query = self.search_edit.text().strip()
        if not query:
            self._on_clear_search()
            return
        records = self.db.search_files(query, self._channel_filter)
        self.cloud_model.set_files(records)
        self.status_bar.showMessage(f"{len(records)} risultati per '{query}'")

    def _on_clear_search(self):
        self.search_edit.clear()
        self._refresh_file_list()

    def _on_create_channel(self):
        from gui.channel_dialog import ChannelDialog
        dialog = ChannelDialog(self.tg_client, self)
        if dialog.exec() == 1:
            self.channel_id = int(dialog.selected_channel_id)
            self.channel_name = getattr(dialog, 'selected_channel_name', '')
            self.config["channel_id"] = str(self.channel_id)
            self.config["channel_name"] = self.channel_name
            save_config(self.config)
            if self.channel_name:
                self.db.insert_or_update_channel(self.channel_id, self.channel_name)
            self._load_channel_names()
            self._update_channel_label()
            self._refresh_cloud()

    def _on_select_download_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Seleziona cartella download", str(self.download_dir))
        if path:
            self.download_dir = Path(path)
            self.config["download_dir"] = str(self.download_dir)
            save_config(self.config)
            self.status_bar.showMessage(f"Cartella download: {self.download_dir}")

    def _on_error(self, message: str):
        QMessageBox.critical(self, "Errore Telegram", message)
        self.status_bar.showMessage(f"Errore: {message}")

    def _on_transfer_op_added(self, op):
        # Non mostrare nella tabella i download intermedi di copia/sposta
        if op.op_type == "download" and op.op_id in self._pending_copy_ops:
            return
        size = 0
        mime_type = ""
        if op.op_type == "upload" and Path(op.file_path).exists():
            size = Path(op.file_path).stat().st_size
            ext = Path(op.file_path).suffix.lower()
            mime_map = {
                ".txt": "text/plain", ".pdf": "application/pdf",
                ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".png": "image/png", ".gif": "image/gif",
                ".mp4": "video/mp4", ".mp3": "audio/mpeg",
                ".zip": "application/zip", ".tar": "application/x-tar",
                ".gz": "application/gzip", ".rar": "application/x-rar",
            }
            mime_type = mime_map.get(ext, "application/octet-stream")
        self.cloud_model.add_transfer(op.op_id, op.original_filename or op.filename, size, mime_type, op.channel_id, op.op_type)

    def _on_transfer_done(self, op_id: str, op_type: str, success: bool, msg: str, filename: str):
        self.cloud_model.remove_transfer(op_id)

        # Gestione catena copia/sposta: download → upload → (delete)
        if op_id in self._pending_copy_ops:
            info = self._pending_copy_ops.pop(op_id)
            if op_type == "download" and success:
                # Download completato: avvia upload verso il canale di destinazione
                local_path = msg  # percorso file scaricato
                new_op_id = self.transfer_manager.add_upload(
                    info['dest_channel'], local_path
                )
                self._pending_copy_ops[new_op_id] = info
                self.transfer_dialog.show()
            elif op_type == "upload" and success:
                # Upload completato: pulisci file temp e, se sposta, elimina sorgente
                try:
                    Path(msg).unlink(missing_ok=True)
                except OSError:
                    pass
                if info['is_move']:
                    # Se dest == current, _on_file_deleted farebbe un refresh ridondante
                    if info['dest_channel'] == self.channel_id:
                        self._suppress_deleted_refresh.add(info['message_id'])
                    self.tg_client.delete_file(
                        info['source_channel'], info['message_id']
                    )
                self._notify_transfer_done(
                    "upload", info.get('original_filename', filename)
                )
                # Refresh: canale destinazione (per popolare DB e aggiornare vista).
                # Chiamiamo UN SOLO metodo per evitare race condition:
                # _refresh_channel_db disconnette _on_file_list_ready e usa un handler one-shot.
                if info['dest_channel'] == self.channel_id:
                    self._refresh_cloud()
                else:
                    self._refresh_channel_db(info['dest_channel'])
            elif not success:
                # Fallimento: notifica errore e pulisci eventuale file temporaneo
                self._notify_transfer_failed(
                    op_type, info.get('original_filename', filename), msg
                )
                if op_type == "upload":
                    try:
                        Path(msg).unlink(missing_ok=True)
                    except OSError:
                        pass
            # Non chiamare _refresh_cloud / _refresh_local_tree qui:
            # per download non serve, per upload è già chiamato sopra
            return

        if success:
            self._notify_transfer_done(op_type, filename)
        if success and op_type == "upload":
            self._refresh_cloud()
        if success:
            # Rigenera il treeview locale per aggiornare dimensioni file
            self._refresh_local_tree()

    def _notify_transfer_done(self, op_type: str, filename: str):
        QApplication.beep()
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon.showMessage(
                "TGM Drive",
                f"{'⬆ Upload' if op_type == 'upload' else '⬇ Download'} completato: {filename}",
                QSystemTrayIcon.MessageIcon.Information,
                3000
            )

    def _notify_transfer_failed(self, op_type: str, filename: str, error_msg: str):
        """Notifica errore per operazioni copia/sposta fallite."""
        label = "Upload" if op_type == "upload" else "Download"
        short_error = error_msg[:120] if error_msg else "errore sconosciuto"
        self.status_bar.showMessage(f"❌ {label} fallito: {filename} — {short_error}")
        QApplication.beep()
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon.showMessage(
                "TGM Drive — Operazione fallita",
                f"{label} di '{filename}' fallito\n{short_error}",
                QSystemTrayIcon.MessageIcon.Warning,
                5000
            )

    def _show_transfer_dialog(self):
        self.transfer_dialog.show()
        self.transfer_dialog.raise_()
        self.transfer_dialog.activateWindow()

    def _load_channel_names(self):
        channels = self.db.get_channels()
        names = {ch["channel_id"]: ch["channel_name"] for ch in channels}
        self.cloud_model.set_channel_names(names)
        self._update_channel_filter_combo(channels)

    def _update_channel_filter_combo(self, channels: list):
        self.channel_filter_combo.clear()
        self.channel_filter_combo.addItem("📁 Tutti i canali", 0)
        self.channel_filter_combo.addItem("📁 Canali con upload", -1)
        upload_ch_ids = self.db.get_files_channel_ids()
        upload_ch_ids_set = set(upload_ch_ids)
        for ch in channels:
            self.channel_filter_combo.addItem(ch["channel_name"], ch["channel_id"])
            upload_ch_ids_set.discard(ch["channel_id"])
        # Add any channels that have uploads but aren't in the channels table
        for ch_id in sorted(upload_ch_ids_set):
            self.channel_filter_combo.addItem(self.db.get_channel_name(ch_id), ch_id)
        # Default: Canali con upload se ci sono file con upload
        if upload_ch_ids:
            idx = self.channel_filter_combo.findData(-1)
            self.channel_filter_combo.setCurrentIndex(idx)
            self._channel_filter = -1
        else:
            self.channel_filter_combo.setCurrentIndex(0)
            self._channel_filter = 0

    def _on_channel_filter_changed(self):
        self._channel_filter = self.channel_filter_combo.currentData()
        self._refresh_file_list()

    def _on_channels_loaded(self, channels: list):
        for ch in channels:
            self.db.insert_or_update_channel(ch["id"], ch["title"])
        self._load_channel_names()
        self._load_favorite_channels()

    def _load_favorite_channels(self):
        favs = self.db.get_favorite_channels()
        self._update_channel_bar(favs)
        self._update_drop_channel_combo()

    def _update_drop_channel_combo(self):
        try:
            self.drop_channel_combo.currentIndexChanged.disconnect(self._on_drop_channel_changed)
        except TypeError:
            pass
        self.drop_channel_combo.clear()
        favs = self.db.get_favorite_channels()
        if not favs:
            self.drop_channel_combo.addItem("📢 Nessun canale preferito", 0)
        for ch in favs:
            self.drop_channel_combo.addItem(ch["display_name"], ch["channel_id"])
        # Also add current channel if not in favorites
        if self.channel_id and self.channel_id not in {ch["channel_id"] for ch in favs}:
            self.drop_channel_combo.addItem(
                self.db.get_channel_name(self.channel_id), self.channel_id
            )
        self.drop_channel_combo.currentIndexChanged.connect(self._on_drop_channel_changed)
        # Set default
        if self.channel_id:
            idx = self.drop_channel_combo.findData(self.channel_id)
            if idx >= 0:
                self.drop_channel_combo.setCurrentIndex(idx)
                self._drop_upload_channel_id = self.channel_id
        # Propagate target names to the SmartDropArea
        ch_name = (
            self.drop_channel_combo.currentText()
            or (self.db.get_channel_name(self.channel_id) if self.channel_id else "canale selezionato")
        )
        dl_name = self._drop_download_dir.name if self._drop_download_dir else self.download_dir.name
        self.drop_area.set_drop_targets(ch_name, dl_name)

    def _on_drop_channel_changed(self):
        self._drop_upload_channel_id = self.drop_channel_combo.currentData()
        ch_name = self.drop_channel_combo.currentText()
        dl_name = self._drop_download_dir.name if self._drop_download_dir else self.download_dir.name
        self.drop_area.set_drop_targets(ch_name, dl_name)

    def _on_drop_select_download_dir(self):
        path = QFileDialog.getExistingDirectory(
            self, "Seleziona cartella download per drop box", str(self._drop_download_dir)
        )
        if path:
            self._drop_download_dir = Path(path)
            self.drop_dir_btn.setToolTip(f"Download in: {self._drop_download_dir}")
            ch_name = self.drop_channel_combo.currentText()
            self.drop_area.set_drop_targets(ch_name, self._drop_download_dir.name)

    def _on_fav_channel_clicked(self, channel_id: int, channel_name: str):
        self.channel_id = channel_id
        self.channel_name = channel_name
        self.config["channel_id"] = str(channel_id)
        self.config["channel_name"] = channel_name
        save_config(self.config)
        # Defer bar rebuild to avoid calling deleteLater on the clicked button
        # while its signal handler is still running (PyQt crash pattern)
        QTimer.singleShot(0, self._update_channel_label)
        QTimer.singleShot(0, self._update_drop_channel_combo)
        self._refresh_cloud()

    # ── Tag handlers ───────────────────────────────────────────────

    def _on_tag_chip_clicked(self, tag_name: str):
        """Quando l'utente clicca un chip tag, filtra i file."""
        self._current_tag_filter = tag_name
        if tag_name == "":
            self._refresh_file_list()
        else:
            records = self.db.get_files_by_tag(tag_name, self._channel_filter)
            self.cloud_model.set_files(records)
            self._update_cloud_info_label()
            self.status_bar.showMessage(
                f"{len(records)} file con tag '{tag_name}'"
            )

    def _load_tag_list(self):
        """Popola il TagChipWidget e il drop_tag_combo con i tag disponibili."""
        tags = self.db.get_tags()
        tag_names = [t['tag_name'] for t in tags]
        self.tag_chip_widget.set_tags(tag_names)
        self._tag_delegate.set_tags(tag_names)
        self.drop_tag_combo.clear()
        self.drop_tag_combo.addItem("🏷️ Nessun tag", "")
        for t in tags:
            self.drop_tag_combo.addItem(f"🏷️ {t['tag_name']}", t['tag_name'])

    def _on_tag_cell_changed(self, top_left, bottom_right):
        """Quando l'utente modifica il tag nella cella della tabella."""
        if top_left.column() != 6:
            return
        for row in range(top_left.row(), bottom_right.row() + 1):
            index = self.cloud_model.index(row, 6)
            file = self.cloud_model.get_file(index)
            if file and file.message_id > 0:
                self.db.update_file_tag(file.message_id, file.tags or "")
        if self._current_tag_filter:
            self._on_tag_chip_clicked(self._current_tag_filter)

    def _on_open_tags_settings(self):
        """Apre il tab Tags nel dialog impostazioni."""
        self._open_settings_dialog(initial_tab=SettingsDialog.TAB_TAGS)

    def _open_settings_dialog(self, initial_tab: int = 0):
        dialog = SettingsDialog(self.config, self.db, self.tg_client, self, initial_tab=initial_tab)
        dialog.settings_applied.connect(self._on_settings_applied)
        dialog.disconnect_requested.connect(self._on_disconnect_requested)
        dialog.reconnect_requested.connect(self._on_reconnect_requested)
        dialog.exec()

    def _on_open_settings(self):
        self._open_settings_dialog(initial_tab=SettingsDialog.TAB_UI)

    def _on_open_favorites(self):
        self._open_settings_dialog(initial_tab=SettingsDialog.TAB_FAVORITES)

    def _on_settings_applied(self, config: dict):
        self.config = config
        self._load_favorite_channels()
        self._load_tag_list()
        self._refresh_cloud()

    def _on_disconnect_requested(self):
        self.tg_client.stop()
        self.status_bar.showMessage("Sessione disconnessa")

    def _on_reconnect_requested(self):
        self.tg_client.stop()
        self.tg_client.wait()
        self.tg_client.start()
        self.status_bar.showMessage("Riconnessione in corso...")

    def _update_channel_label(self):
        favs = self.db.get_favorite_channels()
        self._update_channel_bar(favs)

    def _update_channel_bar(self, favs):
        # Clear existing buttons
        while self.channel_bar_layout.count():
            item = self.channel_bar_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not favs:
            placeholder = QLabel("Nessun canale preferito")
            placeholder.setStyleSheet("color: #888; font-style: italic; padding: 6px;")
            self.channel_bar_layout.addWidget(placeholder)
            add_btn = QPushButton("➕ Aggiungi canali preferiti")
            add_btn.setMaximumHeight(34)
            add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            add_btn.setStyleSheet(
                "QPushButton { background-color: #4CAF50; color: white; border: none; border-radius: 6px; padding: 6px 14px; font-weight: bold; }"
                "QPushButton:hover { background-color: #45a049; }"
            )
            add_btn.setToolTip("Apri la gestione canali preferiti")
            add_btn.clicked.connect(self._on_open_favorites)
            self.channel_bar_layout.addWidget(add_btn)
        else:
            for ch in favs:
                btn = QPushButton(ch.get('display_name', ch.get('channel_name', str(ch['channel_id']))))
                btn.setCheckable(True)
                btn.setMaximumHeight(34)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                ch_id = ch['channel_id']
                btn.clicked.connect(lambda checked, cid=ch_id, cname=ch.get('display_name', ch.get('channel_name', '')): self._on_fav_channel_clicked(cid, cname))
                if ch_id == self.channel_id:
                    btn.setChecked(True)
                    btn.setStyleSheet(
                        "QPushButton { background-color: #2196F3; color: white; border: none; border-radius: 6px; padding: 6px 14px; font-weight: bold; }"
                        "QPushButton:hover { background-color: #1976D2; }"
                    )
                else:
                    btn.setChecked(False)
                    btn.setStyleSheet(
                        "QPushButton { background-color: #555; color: white; border: none; border-radius: 6px; padding: 6px 14px; }"
                        "QPushButton:hover { background-color: #777; }"
                    )
                self.channel_bar_layout.addWidget(btn)
            add_btn = QPushButton("➕")
            add_btn.setMaximumHeight(34)
            add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            add_btn.setStyleSheet(
                "QPushButton { background-color: #4CAF50; color: white; border: none; border-radius: 6px; padding: 6px 14px; font-weight: bold; }"
                "QPushButton:hover { background-color: #45a049; }"
            )
            add_btn.setToolTip("Gestisci canali preferiti")
            add_btn.clicked.connect(self._on_open_favorites)
            self.channel_bar_layout.addWidget(add_btn)
        self.channel_bar_layout.addStretch()

    def closeEvent(self, event):
        self.tg_client.stop()
        event.accept()
