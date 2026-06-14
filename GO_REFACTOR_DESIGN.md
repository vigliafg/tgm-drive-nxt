# TGM Drive — Refactoring Design: Python → Go

> **Hypothetical refactoring** of the PyQt6 application into a Go-based stack. This document maps the current architecture, selects Go libraries, and proposes a project structure.

---

## 1. Current Python Architecture (for reference)

| Module | Responsibility | Stack |
|---|---|---|
| `main.py` | Entry point, app lifecycle, OTP flow | PyQt6 `QApplication`, `QEventLoop` |
| `config.py` | JSON config in `~/.tgm_drive/` | `pathlib`, `json` |
| `database.py` | SQLite metadata + search | `sqlite3`, `dataclasses` |
| `telegram_client.py` | MTProto client in background thread | `Telethon` (async) inside `QThread` + `asyncio` loop |
| `gui/auth_dialog.py` | Credentials dialog | PyQt6 `QDialog` |
| `gui/main_window.py` | File manager UI (splitter, tree, table, preview) | PyQt6 `QMainWindow`, `QFileSystemModel`, `QTableView`, `QTreeView`, drag & drop |
| `gui/cloud_model.py` | Qt model for cloud file list | `QAbstractTableModel` |

---

## 2. Go Technology Choices

### 2.1 Telegram MTProto Client

**Choice: `github.com/gotd/td`**
- Pure Go (no CGO), full MTProto 2.0, actively maintained
- Sub-packages: `uploader` (progress callbacks), `downloader` (CDN, retries)
- Natural concurrency via goroutines

**Rejected:**
- Bot API libraries — 50MB limit insufficient
- `libtdjson` bindings — CGO overhead, harder cross-compilation

### 2.2 GUI Framework

**Two viable paths are presented:**

#### Option A — Fyne (Native Go, simplest)
- `github.com/fyne-io/fyne`
- Retained-mode widgets: `widget.Tree`, `widget.Table`, `widget.ProgressBar`
- Built-in drag & drop, file dialogs, single static binary
- **Pros:** 100% Go, fast to build, easy to bind to Go backend
- **Cons:** Less polished than web-based UIs, table/tree virtualization is basic

#### Option B — Wails (Web frontend + Go backend)
- `github.com/wailsapp/wails`
- Frontend: React/Vue + HTML5 drag & drop + TanStack Table for high-performance grids
- Backend: Go with `gotd/td` + SQLite + `wails.Events` for progress signals
- **Pros:** Pixel-perfect UI, excellent data tables, rich ecosystem
- **Cons:** Requires HTML/CSS/JS knowledge, heavier bundle

**Recommendation:**
- **Fyne** if you want a quick, native desktop refactor with minimal context switching
- **Wails** if you want a modern, professional file manager look (like a web app)

### 2.3 Database

- `github.com/mattn/go-sqlite3` (CGO) or `modernc.org/sqlite` (pure Go, preferred)
- `database/sql` standard library for queries
- Schema remains identical to the Python version

### 2.4 Configuration

- Simple JSON: `encoding/json` + `os.UserHomeDir()`
- Or `github.com/spf13/viper` if you want env vars / defaults

---

## 3. Go Project Structure

```
tgm-drive-go/
├── go.mod
├── main.go
├── internal/
│   ├── config/
│   │   └── config.go        # JSON config + paths
│   ├── db/
│   │   └── db.go            # SQLite schema + CRUD + search
│   ├── telegram/
│   │   └── client.go        # gotd/td wrapper, goroutines, progress channels
│   └── gui/                 # or wails/ if using Wails
│       └── app.go
├── frontend/                # Only for Wails
│   ├── src/
│   └── package.json
└── assets/
    └── icon.png
```

---

## 4. Module Mapping (Python → Go)

### 4.1 Config (`config.py` → `internal/config/config.go`)

```go
package config

import (
    "encoding/json"
    "os"
    "path/filepath"
)

var (
    ConfigDir  = filepath.Join(os.UserHomeDir(), ".tgm_drive")
    ConfigFile = filepath.Join(ConfigDir, "config.json")
    SessionFile = filepath.Join(ConfigDir, "tgm_drive")
)

type Config struct {
    APIID       string `json:"api_id"`
    APIHash     string `json:"api_hash"`
    Phone       string `json:"phone"`
    ChannelID   int64  `json:"channel_id"`
    ChannelName string `json:"channel_name"`
    DownloadDir string `json:"download_dir"`
    SessionOK   bool   `json:"session_ok"`
}

func Load() (*Config, error) { ... }
func Save(c *Config) error { ... }
```

### 4.2 Database (`database.py` → `internal/db/db.go`)

Schema stays identical. Use `modernc.org/sqlite` for pure Go.

```go
package db

import (
    "database/sql"
    "fmt"
    "time"

    _ "modernc.org/sqlite"
)

type FileRecord struct {
    ID           int64
    MessageID    int64
    Filename     string
    Size         int64
    MimeType     string
    UploadDate   string
    Tags         string
    LocalPath    *string
    TelegramPath *string
}

type Database struct {
    db *sql.DB
}

func New(dbPath string) (*Database, error) { ... }
func (d *Database) InsertFile(...) error { ... }
func (d *Database) GetAllFiles() ([]FileRecord, error) { ... }
func (d *Database) SearchFiles(query string) ([]FileRecord, error) { ... }
func (d *Database) DeleteFile(messageID int64) error { ... }
```

### 4.3 Telegram Client (`telegram_client.py` → `internal/telegram/client.go`)

Key change: no `QThread` + `asyncio` hack. Go goroutines + `context.Context` are native.

```go
package telegram

import (
    "context"
    "fmt"
    "path/filepath"

    "github.com/gotd/td/telegram"
    "github.com/gotd/td/telegram/downloader"
    "github.com/gotd/td/telegram/uploader"
    "github.com/gotd/td/tg"
)

type Client struct {
    apiID       int
    apiHash     string
    sessionPath string
    client      *telegram.Client
    uploader    *uploader.Uploader
    downloader  *downloader.Downloader
    
    // Channels for cross-goroutine communication with GUI
    UploadProgress chan Progress
    UploadDone     chan Result
    DownloadProgress chan Progress
    DownloadDone   chan Result
    FileListReady  chan []CloudFile
    ErrorOccurred  chan error
}

type Progress struct {
    Current int64
    Total   int64
}

type Result struct {
    Success bool
    Path    string
    Err     error
}

type CloudFile struct {
    MessageID int64
    Filename  string
    Size      int64
    MimeType  string
    Date      string
}

func NewClient(apiID int, apiHash, sessionPath string) *Client { ... }

func (c *Client) Connect(ctx context.Context) error {
    // gotd/td handles auth, OTP, session persistence
    // It provides a callback for phone code requests
}

func (c *Client) ListFiles(ctx context.Context, channelID int64) ([]CloudFile, error) {
    // goroutine-safe, returns via channel or directly
}

func (c *Client) UploadFile(ctx context.Context, channelID int64, filePath string) {
    // Runs in a goroutine, reports progress via channel
    // uploader.WithProgress(callback) -> callback sends to c.UploadProgress
}

func (c *Client) DownloadFile(ctx context.Context, channelID, messageID int64, outputDir string) {
    // downloader -> progress channel -> GUI
}

func (c *Client) DeleteFile(ctx context.Context, channelID, messageID int64) error { ... }
```

**Critical difference:** In Go, `context.Context` replaces the `QEventLoop` + `asyncio` complexity. Cancellation, timeouts, and OTP prompts are handled naturally.

### 4.4 GUI — Fyne Option (`gui/main_window.py` → `internal/gui/app.go`)

```go
package gui

import (
    "fyne.io/fyne/v2"
    "fyne.io/fyne/v2/app"
    "fyne.io/fyne/v2/container"
    "fyne.io/fyne/v2/dialog"
    "fyne.io/fyne/v2/widget"
    "fyne.io/fyne/v2/storage"
)

type App struct {
    fyneApp        fyne.App
    mainWindow     fyne.Window
    tgClient       *telegram.Client
    db             *db.Database
    
    localTree      *widget.Tree        // maps to QFileSystemModel + QTreeView
    cloudTable     *widget.Table       // maps to QAbstractTableModel + QTableView
    progressBar    *widget.ProgressBar
    searchEntry    *widget.Entry
    previewImage   *canvas.Image
    previewText    *widget.TextGrid
    statusLabel    *widget.Label
}

func New(tgClient *telegram.Client, database *db.Database) *App { ... }

func (a *App) Run() {
    a.mainWindow.ShowAndRun()
}

// Fyne equivalents:
// - QTreeView + QFileSystemModel -> widget.Tree with custom childUIDs
// - QTableView + QAbstractTableModel -> widget.Table with length/cell/update funcs
// - QProgressBar -> widget.ProgressBar
// - QLineEdit -> widget.Entry
// - QMessageBox -> dialog.NewInformation / dialog.NewConfirm
// - QFileDialog -> dialog.NewFileOpen / dialog.NewFolderOpen
// - Drag & Drop -> widget.Draggable interface (or custom container)
// - QShortcut -> desktop.KeyShortcut (limited)
```

**Fyne drag & drop:** `fyne.Draggable` interface exists, but full external file drop (from OS) is limited on some platforms. A dedicated drop target widget or file dialog is more reliable.

### 4.5 GUI — Wails Option (React + Go)

```go
// Go backend: app.go
package main

import (
    "context"
    "github.com/wailsapp/wails/v2/pkg/runtime"
)

type App struct {
    ctx      context.Context
    tgClient *telegram.Client
    db       *db.Database
}

func (a *App) Startup(ctx context.Context) {
    a.ctx = ctx
    // Connect to Telegram
}

// Wails-exposed methods (callable from JS)
func (a *App) ListCloudFiles() ([]db.FileRecord, error) { ... }
func (a *App) UploadFile(filePath string) error { ... }
func (a *App) DownloadFile(messageID int64) error { ... }
func (a *App) DeleteFile(messageID int64) error { ... }
func (a *App) SearchFiles(query string) ([]db.FileRecord, error) { ... }

// Events emitted to JS
// runtime.EventsEmit(a.ctx, "upload:progress", current, total)
// runtime.EventsEmit(a.ctx, "upload:done", path)
```

```typescript
// React frontend (simplified)
import { EventsOn, EventsEmit } from "../wailsjs/runtime";

function App() {
  const [files, setFiles] = useState([]);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    EventsOn("upload:progress", (current, total) => {
      setProgress((current / total) * 100);
    });
    EventsOn("upload:done", () => refreshFiles());
  }, []);

  return (
    <div className="split-pane">
      <LocalExplorer />   {/* HTML5 <input type="file" webkitdirectory /> or custom tree */}
      <CloudTable data={files} onDownload={...} onDelete={...} />
      <PreviewPanel />
      <ProgressBar value={progress} />
    </div>
  );
}
```

---

## 5. Concurrency Model in Go

| Python (Current) | Go (Proposed) |
|---|---|
| `QThread` + `asyncio.new_event_loop()` | Native goroutine + `context.Context` |
| `pyqtSignal` for thread-safe UI updates | Go channels (or Wails `runtime.EventsEmit`) |
| `asyncio.run_coroutine_threadsafe` | Direct goroutine spawn |
| `asyncio.Event` for OTP wait | `context.WithCancel` or blocking channel receive |
| `asyncio.sleep(0.1)` loop to keep thread alive | `select {}` on a `<-ctx.Done()` or channel |

**OTP flow in Go:**
```go
// In main or goroutine
ctx := context.Background()

// gotd/td auth flow: when phone code is required, the library calls a callback
err := client.Run(ctx, func(ctx context.Context) error {
    // If not authorized, prompt for OTP
    code, err := gui.PromptOTP("Inserisci il codice OTP...")
    if err != nil { return err }
    return client.Auth().Phone(ctx, phone, code)
})
```

---

## 6. Migration Plan (Hypothetical)

| Phase | Effort | Tasks |
|---|---|---|
| **1. Scaffold** | 1–2 days | `go mod init`, setup `gotd/td`, `modernc.org/sqlite`, basic `main.go` |
| **2. Backend** | 3–4 days | Port `config`, `database`, `telegram_client` to Go packages |
| **3. GUI (Fyne)** | 5–7 days | `widget.Tree`, `widget.Table`, `widget.ProgressBar`, drag & drop, dialogs |
| **3. GUI (Wails)** | 7–10 days | React frontend, table virtualization, HTML5 DnD, Go→JS event bridge |
| **4. Integration** | 2–3 days | Wire backend to GUI, test upload/download/delete, OTP flow |
| **5. Polish** | 2–3 days | Error handling, logging, build scripts, release binaries |

**Total estimate:** ~15–20 days (Fyne), ~20–25 days (Wails)

---

## 7. Key Trade-offs

| Aspect | Python/PyQt6 (Current) | Go/Fyne (Option A) | Go/Wails (Option B) |
|---|---|---|---|
| **Binary size** | ~50–80 MB (PyQt6 + Python) | ~15–30 MB | ~20–40 MB (with webview) |
| **Startup time** | Slow (Python interpreter) | Fast (native binary) | Fast (native binary) |
| **Cross-compile** | Hard (PyInstaller) | Easy (`GOOS`/`GOARCH`) | Easy (`wails build`) |
| **GUI richness** | Excellent (Qt6) | Good (basic widgets) | Excellent (web stack) |
| **Memory** | High | Low | Medium (webview overhead) |
| **Dev speed** | Fast (Python) | Medium | Medium (JS + Go) |
| **Telegram lib** | Telethon (mature) | gotd/td (mature) | gotd/td (mature) |
| **Drag & Drop** | Excellent (Qt) | Limited (OS-dependent) | Excellent (HTML5) |

---

## 8. Recommendation

- **If the goal is a lightweight, single-binary, fast desktop app** → **Go + Fyne**
- **If the goal is a modern, web-like UI with advanced data grids** → **Go + Wails + React**
- **If the current Python app works well** → Keep it; the migration cost is high for marginal gains unless you need smaller binaries or faster startup

---

*Document version: 2026-06-09 | Based on TGM Drive Python v1.0*
