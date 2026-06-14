# TGM Drive — Project Context

> **Purpose**: Complete reference for resuming work. Contains architecture, source code, known issues, and next steps.

---

## 1. Architecture

- **GUI**: PyQt6 (QMainWindow, QTreeView, QTableView, QFileSystemModel, Drag&Drop)
- **Telegram API**: MTProto via Telethon (user account, not bot) — supports files up to 2GB/4GB
- **Database**: SQLite (`~/.tgm_drive/files.db`) for file metadata, channels, favorites, tags, search, and offline browsing
- **Threading**: `TelegramClientThread` (QThread + asyncio loop) to avoid blocking the GUI
- **Config**: JSON file (`~/.tgm_drive/config.json`) + session file (`~/.tgm_drive/tgm_drive.session`)
- **Virtual env**: `.venv/` in project root with PyQt6 6.11.0 and Telethon 1.43.2
- **Transfer Manager**: `TransferManager` (QObject) with queue, speed tracking, and progress signals
- **Transfer Dialog**: `TransferDialog` (QDialog) showing queue, progress bars, speed info, auto-clear
- **Setup Wizard**: 5-page wizard (Welcome → Credentials → OTP → Channel → Favorites) for first-run setup
- **Install Scripts**: Platform-specific installers (`scripts/install-linux.sh`, `scripts/install-macos.sh`, `scripts/install-windows.bat`) that create venv, install deps, and set up a global `tgm-drive` launcher command

---

## 2. File Structure

```
.
├── main.py                    # Entry point, OTP flow, wizard or direct connection, launches MainWindow
├── config.py                  # JSON config management (~/.tgm_drive/config.json)
├── database.py                # SQLite: CRUD for files, channels, favorites, tags + search + migrations
├── telegram_client.py         # MTProto client (Telethon) in QThread + asyncio event loop
├── requirements.txt           # PyQt6>=6.4.0, telethon>=1.28.0
├── README.md                  # User-facing documentation (Italian)
├── PROJECT_CONTEXT.md         # This file — developer reference
├── TAG_SYSTEM_DESIGN.md       # Detailed design doc for the tagging system
├── GO_REFACTOR_DESIGN.md      # Feasibility study: Python/PyQt6 → Go (Fyne or Wails)
├── FYNE_COMPROMISE.md         # Fyne vs PyQt6 trade-off analysis
├── LICENSE                    # GPL-3.0
├── .gitignore
├── .gitattributes
├── scripts/
│   ├── install-linux.sh       # Installer & launcher per Linux → ~/.local/bin/tgm-drive
│   ├── install-macos.sh       # Installer & launcher per macOS → /usr/local/bin/tgm-drive
│   └── install-windows.bat    # Installer & launcher per Windows → scripts/tgm-drive.bat
└── gui/
    ├── __init__.py             # Empty (package marker)
    ├── auth_dialog.py          # Initial auth dialog (API ID, Hash, Phone)
    ├── channel_dialog.py       # Channel selector dialog with search and manual ID fallback
    ├── main_window.py          # Main window: local explorer, cloud table, drop area, tag chips, channel bar
    ├── cloud_model.py          # Qt QAbstractTableModel for cloud file list + TagDelegate (inline combo)
    ├── transfer_manager.py     # Async transfer queue with speed tracking (MB/s)
    ├── transfer_dialog.py      # Transfer queue dialog: progress bars, speed, auto-clear
    ├── setup_wizard.py         # First-run wizard: 5 guided pages (Welcome → Credentials → OTP → Channel → Favorites)
    ├── settings_dialog.py      # Settings dialog: 4 tabs (UI, Telegram, Favorites, Tags) + FavoriteChannelsTab + TagsTab
    ├── destination_dialog.py   # Destination channel selector for copy/move operations
    ├── tag_chip_widget.py      # Compact tag chip/pill widget with FlowLayout for multi-row wrapping
    └── (no other files)
```

---

## 3. Key Features Implemented

| Feature | Status |
|---|---|
| Upload via button / drag & drop (local files) | ✅ |
| Download via button / double-click / drag & drop (cloud → drop area) | ✅ |
| Transfer queue with progress, speed (MB/s), ETA row | ✅ |
| Transfer dialog with auto-clear, clear all, clear completed | ✅ |
| System tray notification + beep on transfer completion | ✅ |
| Multi-channel support: select, filter, channel name labels | ✅ |
| ⭐ Favorite channels bar with quick-switch buttons (inline in MainWindow) | ✅ |
| 📋 Copy / 📦 Move files between channels (download → upload pipeline) | ✅ |
| Substring search with LIKE wildcard escape (`_` and `%`) | ✅ |
| File preview (text / image placeholder) | ✅ |
| Drag & drop from cloud table to drop box (custom MIME type) | ✅ |
| Drag & drop from local tree to drop box | ✅ |
| Transfer rows in main file list (italic, badge icons) | ✅ |
| Multi-select checkboxes with batch delete/copy/move | ✅ |
| 🏷️ Single-tag per file: assign on upload or edit inline (combo delegate) | ✅ |
| Tag chip widget: clickable pill filter, cross-channel, flow layout | ✅ |
| Tag management: create, rename, delete, reorder from Settings | ✅ |
| Setup wizard: 5-page guided first-run flow with OTP retry | ✅ |
| Settings dialog: UI theme/font/size, Telegram credentials, Favorites, Tags | ✅ |
| Dark/Light/System theme support | ✅ |
| Adjustable font size (8-24 pt) | ✅ |
| Channel creation from within the app | ✅ |
| Session persistence (avoids re-auth on restart) | ✅ |
| DB auto-migration (ALTER TABLE for new columns) | ✅ |
| Global launcher command `tgm-drive` via install scripts | ✅ |

---

## 4. Known Issues

| Issue | Severity | Notes |
|---|---|---|
| Treeview collapses after model refresh | Minor | `directoryLoaded` + `QTimer` not always restoring expansion. File: `_refresh_local_tree` |
| `_clear_all` only clears UI, not TransferManager queue | Minor | Manager continues processing. Acceptable for UX. |
| `FavoriteChannelsBar` standalone widget removed (dead code) | — | Handled inline in MainWindow._update_channel_bar() |
| No unit tests | Medium | Entire codebase relies on manual testing |

---

## 5. Testing Status

- **Syntax check**: All 13 `.py` files pass `py_compile` ✅
- **Not yet tested live** with real Telegram credentials
- **Transfer dialog**: UI tested visually, queue logic verified
- **Drag & drop**: Internal drag verified; external (Dolphin) verified

---

## 6. Next Steps (User's Plans)

1. **Richer transfer box**: stats, ETA, pause/cancel per file
2. **File collision handling**: overwrite, rename, skip on re-upload/re-download
3. **Unit tests**: pytest coverage for database, transfer manager, config

---

## 7. Quick Commands

```bash
# Dopo l'installazione con lo script:
tgm-drive

# In sviluppo (manuale):
cd /home/vigliafg/Documenti/GitHub/tgm-drive-nxt
source .venv/bin/activate
python main.py
```

---

*Updated: 2026-06-14 (install scripts added)*
