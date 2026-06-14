# TGM Drive — Project Context

> **Purpose**: Complete reference for resuming work. Contains architecture, source code, known issues, and next steps.

---

## 1. Architecture

- **GUI**: PyQt6 (QMainWindow, QTreeView, QTableView, QFileSystemModel, Drag&Drop)
- **Telegram API**: MTProto via Telethon (user account, not bot) — supports files up to 2GB/4GB
- **Database**: SQLite (`~/.tgm_drive/files.db`) for file metadata, search, and offline browsing
- **Threading**: `TelegramClientThread` (QThread + asyncio loop) to avoid blocking the GUI
- **Config**: JSON file (`~/.tgm_drive/config.json`) + session file (`~/.tgm_drive/tgm_drive.session`)
- **Virtual env**: `.venv/` in project root with PyQt6 6.11.0 and Telethon 1.43.2
- **Transfer Manager**: `TransferManager` (QObject) with queue, speed tracking, and progress signals
- **Transfer Dialog**: `TransferDialog` (QDialog) showing queue, progress bars, speed info, auto-clear

---

## 2. File Structure

```
.
├── main.py
├── config.py
├── database.py
├── telegram_client.py
├── requirements.txt
├── README.md
├── GO_REFACTOR_DESIGN.md
├── FYNE_COMPROMISE.md
├── PROJECT_CONTEXT.md
├── SESSION_LOG.md
└── gui/
    ├── __init__.py
    ├── auth_dialog.py
    ├── channel_dialog.py
    ├── main_window.py
    ├── cloud_model.py
    ├── transfer_manager.py
    └── transfer_dialog.py
```

---

## 3. Key Features Implemented

| Feature | Status |
|---|---|
| Upload via button / drag & drop (local) | ✅ |
| Upload via drag & drop from cloud table | ✅ |
| Download via button / double-click / drag & drop | ✅ |
| Transfer queue with progress & speed | ✅ |
| Transfer dialog with auto-clear, clear all | ✅ |
| System notification + beep on completion | ✅ |
| Multi-channel support (select, filter, label) | ✅ |
| Substring search with underscore escape | ✅ |
| File preview (text / image placeholder) | ✅ |
| Drag & drop from cloud table to drop box | ✅ |
| Drag & drop from local tree to drop box | ✅ |
| Transfer rows in main file list (italic, badge) | ✅ |

---

## 4. Known Issues

| Issue | Severity | Notes |
|---|---|---|
| Treeview collapses after model refresh | Minor | `directoryLoaded` + `QTimer` not always restoring expansion. File: `_refresh_local_tree` |
| `_clear_all` only clears UI, not TransferManager queue | Minor | Manager continues processing. Acceptable for UX. |
| Search placeholder says "sottostringa" | Trivial | Already updated |

---

## 5. Testing Status

- **Syntax check**: All files pass `py_compile` ✅
- **Not yet tested live** with real Telegram credentials
- **Transfer dialog**: UI tested visually, queue logic verified
- **Drag & drop**: Internal drag verified; external (Dolphin) verified

---

## 6. Next Steps (User's Plans)

1. **Richer transfer box**: stats, ETA, pause/cancel per file
2. **File collision handling**: overwrite, rename, skip on re-upload/re-download
3. **Settings dialog**: UI config (theme, font) + Telegram config (API, phone, session)

---

## 7. Quick Commands

```bash
cd /home/vigliafg/Documenti/tgm-drive
source .venv/bin/activate
python main.py
```

---

*Updated: 2026-06-10*
