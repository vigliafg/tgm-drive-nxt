import sys

from PyQt6.QtWidgets import QApplication, QMessageBox

from config import load_config, save_config, SESSION_FILE
from database import Database
from telegram_client import TelegramClientThread
from gui.setup_wizard import SetupWizard
from gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("TGM Drive")
    app.setStyle("Fusion")

    config = load_config()
    db = Database()

    tg_client = None
    needs_setup = (
        not config.get("api_id")
        or not config.get("api_hash")
        or not config.get("phone")
        or not config.get("channel_id")
    )

    if needs_setup:
        # ── Wizard di primo avvio ──────────────────────────────────
        wizard = SetupWizard(config, db)

        # Il wizard salva la config e gestisce la connessione internamente.
        # Alla chiusura, wizard_finished ci fornisce config aggiornata e client.
        def on_wizard_finished(new_config, client):
            nonlocal config, tg_client
            config = new_config
            tg_client = client
            # Non chiamiamo accept() qui: il wizard lo fa dopo aver emesso il segnale

        wizard.wizard_finished.connect(on_wizard_finished)

        if wizard.exec() != 1:
            # Utente ha annullato il wizard
            sys.exit(0)

        # Ricarica config per sicurezza (il wizard salva su disco)
        config = load_config()
    else:
        # ── Configurazione già completa ────────────────────────────
        # Connessione rapida con credenziali esistenti
        api_id = int(config["api_id"])
        api_hash = config["api_hash"]
        phone = config["phone"]

        tg_client = TelegramClientThread(api_id, api_hash, str(SESSION_FILE))
        tg_client.set_phone(phone)

        # Connessione: se l'utente è già autorizzato, non serve OTP.
        # Usiamo un event loop per aspettare la connessione.
        from PyQt6.QtCore import QEventLoop

        connected_ok = False
        otp_loop = QEventLoop()

        def on_otp_required(msg):
            # Caso raro: sessione scaduta, serve OTP anche con config esistente
            from PyQt6.QtWidgets import QInputDialog
            code, ok = QInputDialog.getText(None, "OTP Richiesto", msg)
            if ok and code:
                tg_client.set_otp(code.strip())
            else:
                tg_client.stop()
                otp_loop.quit()
                sys.exit(0)

        def on_connected(ok, msg):
            nonlocal connected_ok
            connected_ok = ok
            otp_loop.quit()

        def on_error(msg):
            otp_loop.quit()

        tg_client.otp_required.connect(on_otp_required)
        tg_client.connected.connect(on_connected)
        tg_client.error_occurred.connect(on_error)

        tg_client.start()
        otp_loop.exec()

        if not connected_ok:
            QMessageBox.critical(None, "Errore", "Connessione a Telegram fallita")
            sys.exit(1)

        config["session_ok"] = True
        save_config(config)

    # ── Avvia la MainWindow ────────────────────────────────────────
    window = MainWindow(tg_client, db, config)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
