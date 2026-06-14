from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QFormLayout
)
from PyQt6.QtCore import Qt


class AuthDialog(QDialog):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("TGM Drive - Autenticazione Telegram")
        self.setMinimumWidth(400)
        self._build_ui()
        self._load_config()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.api_id_edit = QLineEdit()
        self.api_hash_edit = QLineEdit()
        self.phone_edit = QLineEdit()

        self.api_id_edit.setPlaceholderText("12345")
        self.api_hash_edit.setPlaceholderText("abc123...")
        self.phone_edit.setPlaceholderText("+39333...")

        form.addRow("API ID:", self.api_id_edit)
        form.addRow("API Hash:", self.api_hash_edit)
        form.addRow("Phone:", self.phone_edit)
        layout.addLayout(form)

        info = QLabel(
            "Ottieni API ID e API Hash da <a href='https://my.telegram.org'>my.telegram.org</a>"
        )
        info.setOpenExternalLinks(True)
        info.setWordWrap(True)
        layout.addWidget(info)

        btn_layout = QHBoxLayout()
        self.action_btn = QPushButton("Salva")
        self.action_btn.setDefault(True)
        self.action_btn.clicked.connect(self._on_action)
        self.cancel_btn = QPushButton("Annulla")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(self.action_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

    def _load_config(self):
        self.api_id_edit.setText(self.config.get("api_id", ""))
        self.api_hash_edit.setText(self.config.get("api_hash", ""))
        self.phone_edit.setText(self.config.get("phone", ""))

    def _on_action(self):
        api_id = self.api_id_edit.text().strip()
        api_hash = self.api_hash_edit.text().strip()
        phone = self.phone_edit.text().strip()

        if not api_id or not api_hash or not phone:
            QMessageBox.warning(self, "Errore", "Compila tutti i campi")
            return

        try:
            int(api_id)
        except ValueError:
            QMessageBox.warning(self, "Errore", "API ID deve essere un numero")
            return

        self.accept()
