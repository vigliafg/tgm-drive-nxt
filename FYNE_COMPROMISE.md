# Compromessi Fyne — Esempio Pratico

> Cosa **perdi** se rifattorizzi TGM Drive da PyQt6 → Fyne.

---

## 1. Esploratore Locale (QTreeView → widget.Tree)

**PyQt6:** `QFileSystemModel` scansiona automaticamente il filesystem, carica le cartelle in lazy mode, mostra icone, dimensioni, date, e gestisce migliaia di file senza lag.

**Fyne:** `widget.Tree` richiede che **tu** fornisca ogni nodo. Devi scansionare manualmente con `os.ReadDir` e ricostruire l'albero. **Nessun lazy loading** — se apri `/home` con 10.000 file, l'UI si blocca finché non hai creato tutti i nodi.

```go
// FYNE — esploratore locale (semplificato)
func buildTree(dir string) map[string][]string {
    tree := make(map[string][]string)
    entries, _ := os.ReadDir(dir)
    for _, e := range entries {
        child := filepath.Join(dir, e.Name())
        tree[dir] = append(tree[dir], child)
        if e.IsDir() {
            tree[child] = []string{} // popolare ricorsivamente? lento!
        }
    }
    return tree
}

localTree := widget.NewTree(
    func(id string) bool { return isDir(id) },
    func(id string) bool { return id != "" },
    func(branch bool) fyne.CanvasObject {
        return fyne.NewContainerWithLayout(layout.NewHBoxLayout(), widget.NewIcon(nil), widget.NewLabel("Template"))
    },
    func(id string, branch bool, o fyne.CanvasObject) {
        // aggiorna icona e label... no icona file nativa
    },
)
```

**Compromesso:** Perdi iconografia nativa, lazy loading, e performance su cartelle grandi. Devi implementare una cache.

---

## 2. Tabella Cloud (QTableView → widget.Table)

**PyQt6:** `QAbstractTableModel` con sorting, filtri, resize colonne, selezione multipla, virtual scrolling, alternate row colors.

**Fyne:** `widget.Table` è primitivo. Fornisci solo: `Length()`, `CreateCell()`, `UpdateCell()`, `OnSelected()`. **Nessun sorting**, **nessun filtro**, **nessuna ricerca integrata**, **nessuna selezione multipla di righe** (solo singola cella).

```go
// FYNE — tabella cloud (semplificato)
cloudTable := widget.NewTable(
    func() (int, int) { return len(files), 5 }, // righe, colonne
    func() fyne.CanvasObject { return widget.NewLabel("cella") },
    func(id widget.TableCellID, cell fyne.CanvasObject) {
        label := cell.(*widget.Label)
        f := files[id.Row]
        switch id.Col {
        case 0: label.SetText(f.Filename)
        case 1: label.SetText(formatSize(f.Size))
        case 2: label.SetText(f.MimeType)
        case 3: label.SetText(f.Date)
        case 4: label.SetText(f.Tags)
        }
    },
)

// Per la ricerca: devi rifare la slice `files` e chiamare `cloudTable.Refresh()`
// Per selezione multipla: non esiste. Devi tracciare manualmente quali celle sono selezionate.
```

**Compromesso:** Perdi sort, filtri, selezione multipla, drag & drop tra righe. Devi riscrivere tutto a mano.

---

## 3. Drag & Drop da OS

**PyQt6:** `dragEnterEvent` + `dropEvent` accettano file direttamente da Finder/Nautilus. L'utente trascina e basta.

**Fyne:** **Non supporta drag & drop da OS** (solo interno all'app). Devi usare un pulsante "Seleziona file" o `dialog.NewFileOpen` multiplo.

```go
// FYNE — no drag & drop da OS
btnUpload := widget.NewButton("⬆ Seleziona file", func() {
    d := dialog.NewFileOpen(func(reader fyne.URIReadCloser, err error) {
        if err != nil { return }
        // upload singolo — per multipli, serve un loop
    }, win)
    d.Show()
})

// Per multipli: Fyne non ha dialog multi-file nativo. Devi usare folder dialog o fare N dialog singoli.
```

**Compromesso:** L'utente perde la comodità del drag & drop. L'UX diventa "click → dialog → click → dialog".

---

## 4. Preview

**PyQt6:** `QPixmap` carica immagini di qualsiasi dimensione, `QTextEdit` per file di testo, `QVideoWidget` per video.

**Fyne:** `canvas.Image` carica immagini, ma **senza zoom, scroll, o gestione memoria per file grandi**. Se trascini una foto da 20MB, Fyne la carica interamente in RAM come `image.Image`. Per file di testo, `widget.TextGrid` o `widget.Label` — nessun scroll automatico se il testo è lungo (devi wrappare in `container.Scroll`).

```go
// FYNE — preview immagine
img := canvas.NewImageFromFile("/path/to/20mb.jpg")
img.FillMode = canvas.ImageFillOriginal
// Problema: se l'immagine è 8000x6000, Fyne la scala a schermo intero
// ma consuma ~200MB di RAM. Non c'è "adatta alla finestra" intelligente.
```

**Compromesso:** Preview limitata a immagini piccole. Per video, PDF, o file grandi: nessun supporto nativo.

---

## 5. Riassunto Compromessi

| Funzionalità PyQt6 | Fyne Equivalente | Compromesso |
|---|---|---|
| `QFileSystemModel` + `QTreeView` | `widget.Tree` + `os.ReadDir` | Niente lazy loading, niente icone native, lento su cartelle grandi |
| `QAbstractTableModel` + `QTableView` | `widget.Table` | Niente sort, filtri, selezione multipla, resize colonne |
| Drag & Drop da OS | **Non supportato** | Solo dialog file o drag interno all'app |
| `QPixmap` preview | `canvas.Image` | Niente zoom intelligente, memoria non gestita, niente video/PDF |
| `QProgressBar` | `widget.ProgressBar` | ✅ Equivalente |
| `QLineEdit` + live search | `widget.Entry` + manual refresh | ✅ Fattibile, ma devi gestire la logica a mano |
| `QShortcut` (F5, Delete) | `desktop.KeyShortcut` | ✅ Limitato ma presente |
| `QMessageBox` | `dialog.NewInformation` / `dialog.NewConfirm` | ✅ Equivalente |
| `QFileDialog` | `dialog.NewFileOpen` / `dialog.NewFolderOpen` | ✅ Equivalente, ma manca dialog multi-file |

---

## 6. Verdetto

Con Fyne otterrai:
- ✅ Un **singolo binario nativo**, fast startup, basso consumo RAM
- ✅ Backend Telegram (gotd/td) perfettamente integrato
- ❌ Una **UX molto più grezza**: niente drag & drop da OS, explorer lento, tabella primitiva, preview limitata

**Per chi va bene:** Se l'app è per uso personale e accetti di usare dialog invece di drag & drop, Fyne è sufficiente.
**Per chi NON va bene:** Se vuoi la stessa fluidità di un file manager tipo Finder / Explorer, Fyne **non ce la fa** — serve Wails (o restare su PyQt6).

---

*Esempio pratico: TGM Drive con Fyne sarebbe un'app funzionale ma "minimalista", non un sostituto professionale di Google Drive / Dropbox.*
