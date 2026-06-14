# TGM Drive — Sistema di Tagging dei File

## Documento di Progettazione Dettagliato

### 1. Obiettivo

Consentire all'utente di:
- Assegnare un **tag singolo** a ciascun file durante l'upload o successivamente.
- Filtrare la lista dei file cloud mostrando solo quelli con un determinato tag.
- Il filtro per tag opera su **tutti i canali** contemporaneamente (cross-channel).
- Gestire la lista dei tag (creazione, rinomina, eliminazione) con un'interfaccia analoga a quella dei canali preferiti.

---

### 2. Analisi dello Stato Attuale

#### 2.1 Cosa esiste già

| Componente | Stato | Note |
|---|---|---|
| `files.tags` (SQLite) | ✅ Colonna `TEXT DEFAULT ''` già presente | `database.py` riga 39 |
| `FileRecord.tags` (dataclass) | ✅ Campo `tags: str` | `database.py` riga 19 |
| `insert_file(tags=...)` | ✅ Parametro già accettato | `database.py` riga 82 |
| `search_files()` | ✅ Cerca già nella colonna `tags` via LIKE | `database.py` riga 118 |
| Colonna "Tags" in tabella | ✅ `CloudFileModel.COLUMNS[5] = "Tags"`, `data()` restituisce `file.tags` | `cloud_model.py` righe 10, 123 |
| `FavoriteChannelsTab` | ✅ Pattern UI riutilizzabile: lista sinistra + bottoni + lista destra | `settings_dialog.py` |

#### 2.2 Cosa manca

| Funzionalità | Stato |
|---|---|
| Assegnare tag durante upload (pulsante e drag-drop) | ❌ |
| Modificare il tag di un file già uploadato (cella editabile) | ❌ |
| Tabella `tags` per la lista master dei tag disponibili | ❌ |
| Box/tabella dei tag sotto la cloud table per filtrare | ❌ |
| Tab "Tags" nelle Impostazioni per gestire i tag | ❌ |
| Filtro per tag (cross-channel) | ❌ |

---

### 3. Modifiche al Database (`database.py`)

#### 3.1 Nuova tabella: `tags`

```sql
CREATE TABLE IF NOT EXISTS tags (
    tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
    tag_name TEXT NOT NULL UNIQUE,
    sort_order INTEGER DEFAULT 0
);
```

La tabella `tags` mantiene la **lista master** dei tag disponibili. È analoga alla tabella `favorite_channels`.

#### 3.2 Nuova tabella: `file_tags` (opzionale — valutazione)

**Decisione: NON necessaria.** Poiché il requisito è un tag singolo per file, la colonna `files.tags` già esistente è sufficiente. Se in futuro si volessero tag multipli, si potrà aggiungere una tabella `file_tags` (file_id, tag_id).

#### 3.3 Nuovi metodi nel Database

```python
# database.py — nuovi metodi

def get_tags(self) -> List[Dict]:
    """Restituisce tutti i tag ordinati per sort_order."""
    with self._connect() as conn:
        rows = conn.execute(
            "SELECT tag_id, tag_name, sort_order FROM tags ORDER BY sort_order, tag_name"
        ).fetchall()
        return [dict(r) for r in rows]

def add_tag(self, tag_name: str, sort_order: int = 0) -> int:
    """Aggiunge un tag. Restituisce il tag_id."""
    with self._connect() as conn:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO tags (tag_name, sort_order) VALUES (?, ?)",
            (tag_name, sort_order)
        )
        conn.commit()
        return cursor.lastrowid

def remove_tag(self, tag_id: int):
    """Rimuove un tag e resetta il tag sui file che lo usano."""
    with self._connect() as conn:
        # Ottieni il nome del tag prima di rimuoverlo
        row = conn.execute(
            "SELECT tag_name FROM tags WHERE tag_id = ?", (tag_id,)
        ).fetchone()
        if row:
            # Resetta la colonna tags per tutti i file con quel tag
            conn.execute(
                "UPDATE files SET tags = '' WHERE tags = ?", (row["tag_name"],)
            )
        conn.execute("DELETE FROM tags WHERE tag_id = ?", (tag_id,))
        conn.commit()

def rename_tag(self, tag_id: int, new_name: str):
    """Rinomina un tag e aggiorna tutti i file che lo usano."""
    with self._connect() as conn:
        row = conn.execute(
            "SELECT tag_name FROM tags WHERE tag_id = ?", (tag_id,)
        ).fetchone()
        if row:
            old_name = row["tag_name"]
            # Aggiorna i file
            conn.execute(
                "UPDATE files SET tags = ? WHERE tags = ?",
                (new_name, old_name)
            )
            # Aggiorna il tag
            conn.execute(
                "UPDATE tags SET tag_name = ? WHERE tag_id = ?",
                (new_name, tag_id)
            )
        conn.commit()

def update_file_tag(self, message_id: int, tag_name: str):
    """Aggiorna il tag di un singolo file."""
    with self._connect() as conn:
        conn.execute(
            "UPDATE files SET tags = ? WHERE message_id = ?",
            (tag_name, message_id)
        )
        conn.commit()

def set_tags(self, tags: List[Dict]):
    """Sostituisce l'intera lista tag (per salvataggio da Settings)."""
    with self._connect() as conn:
        conn.execute("DELETE FROM tags")
        for t in tags:
            conn.execute(
                "INSERT INTO tags (tag_name, sort_order) VALUES (?, ?)",
                (t["tag_name"], t.get("sort_order", 0))
            )
        conn.commit()

def get_files_by_tag(self, tag_name: str, channel_id: int = 0) -> List[FileRecord]:
    """Restituisce tutti i file con un determinato tag (cross-channel)."""
    with self._connect() as conn:
        if channel_id == -1:
            rows = conn.execute(
                "SELECT * FROM files WHERE tags = ? AND channel_id != 0 ORDER BY upload_date DESC",
                (tag_name,)
            ).fetchall()
        elif channel_id:
            rows = conn.execute(
                "SELECT * FROM files WHERE tags = ? AND channel_id = ? ORDER BY upload_date DESC",
                (tag_name, channel_id)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM files WHERE tags = ? ORDER BY upload_date DESC",
                (tag_name,)
            ).fetchall()
        return [FileRecord(**dict(r)) for r in rows]
```

#### 3.4 Inizializzazione DB

Aggiungere la creazione della tabella `tags` in `_init_db()`:

```python
conn.execute(
    """
    CREATE TABLE IF NOT EXISTS tags (
        tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
        tag_name TEXT NOT NULL UNIQUE,
        sort_order INTEGER DEFAULT 0
    )
    """
)
```

---

### 4. Modifiche al Modello Cloud (`gui/cloud_model.py`)

#### 4.1 Tag Delegate per editabilità inline

Creare un `QStyledItemDelegate` che mostri un `QComboBox` quando l'utente clicca sulla cella "Tags":

```python
# Nuova classe in cloud_model.py o file separato gui/tag_delegate.py

from PyQt6.QtWidgets import QStyledItemDelegate, QComboBox
from PyQt6.QtCore import Qt

class TagDelegate(QStyledItemDelegate):
    """Delegate che mostra un QComboBox per la colonna Tags."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tags: List[str] = []  # ["", "tag1", "tag2", ...]

    def set_tags(self, tags: List[str]):
        """Aggiorna la lista dei tag disponibili (incluso stringa vuota per 'nessun tag')."""
        self._tags = [""] + sorted(tags)

    def createEditor(self, parent, option, index):
        combo = QComboBox(parent)
        combo.addItems(self._tags)
        combo.setEditable(False)  # Solo selezione, no testo libero
        combo.currentTextChanged.connect(lambda: self.commitData.emit(combo))
        return combo

    def setEditorData(self, editor, index):
        current = index.data(Qt.ItemDataRole.DisplayRole) or ""
        idx = editor.findText(current)
        if idx >= 0:
            editor.setCurrentIndex(idx)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)
```

#### 4.2 Flag editabili per colonna Tags

Modificare `CloudFileModel.flags()`:

```python
def flags(self, index):
    if not index.isValid():
        return Qt.ItemFlag.NoItemFlags
    base = Qt.ItemFlag.ItemIsEnabled | Qt.ItemIsSelectable
    if index.row() >= len(self._transfers):
        base |= Qt.ItemFlag.ItemIsDragEnabled
    # Rendi la colonna Tags editabile (colonna 5)
    if index.column() == 5:
        base |= Qt.ItemFlag.ItemIsEditable
    return base
```

#### 4.3 Supporto a `setData()` per la colonna Tags

```python
def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
    if role == Qt.ItemDataRole.EditRole and index.column() == 5:
        row = index.row()
        if row < len(self._transfers):
            return False  # Non editabile per transfer rows
        file = self._files[row - len(self._transfers)]
        file.tags = value
        self.dataChanged.emit(index, index, [role])
        return True
    return False
```

---

### 5. Modifiche alla MainWindow (`gui/main_window.py`)

#### 5.1 Layout: Tag Box compatto sotto la Cloud Table

Nella colonna destra, sotto `cloud_table`, aggiungere un box **compatto** (chip/pill orizzontali):

```
┌─ Colonna Destra ───────────────────────────────────────┐
│ ⭐ [btn1] [btn2] [btn3] [+]                            │ ← channel_bar
│ Filtro canale: [combo]                                 │ ← filter
│ 🔍 Cerca: [________] [Cerca] [Reset]                   │ ← search
│ ☁️ Cloud Telegram                                      │
│ ┌────────────────────────────────────────────────────┐ │
│ │ QTableView (cloud_table)                           │ │
│ └────────────────────────────────────────────────────┘ │
│ ┌─ 🏷️ Tag ───────────────────────────────────────┐    │
│ │ Tutti i file, 𝗹𝗮𝘃𝗼𝗿𝗼, personale, progetti, backup│    │ ← NUOVO: tag box
│ └──────────────────────────────────────────────────┘    │   compatto,
│                                            [➕ gestisci] │   1-2 righe max
└──────────────────────────────────────────────────────────┘
```

**Design del TagChipWidget:**

- Un `QWidget` contenitore con layout orizzontale a **flow** (va a capo automaticamente se troppi tag)
- Ogni tag è una `QLabel` cliccabile (cursor a puntatore, padding 2-6px, border-radius 4px)
- Il tag selezionato: **font-weight: bold**, colore più chiaro, sfondo `#555`
- I tag non selezionati: colore `#aaa`, hover → sfondo `#444`
- "Tutti i file" è trattato come un tag speciale (sempre il primo, resetta il filtro)
- Il pulsante `➕` apre le impostazioni → tab Tags
- Altezza: **~30-50px** (vs ~150px del QListWidget) → più spazio per la tabella cloud

**Comportamento:**

| Clic su | Risultato |
|---|---|
| "lavoro" | → "lavoro" in neretto, tabella filtrata per tag "lavoro" |
| "personale" | → switch: "personale" in neretto, "lavoro" torna normale |
| "Tutti i file" | → reset filtro, nessun tag in neretto, mostra tutti |
| tag già selezionato | → deseleziona, torna a "Tutti i file" |
| `➕` | → apre Impostazioni → tab Tags |

#### 5.2 Nuovo widget `TagChipWidget` in `_build_ui()`

```python
# Dopo right_layout.addWidget(self.cloud_table):

# Tag box compatto (chip/pill orizzontali con flow layout)
self.tag_chip_widget = TagChipWidget()
self.tag_chip_widget.tag_clicked.connect(self._on_tag_chip_clicked)
self.tag_chip_widget.manage_requested.connect(self._on_open_tags_settings)
right_layout.addWidget(self.tag_chip_widget)
```

#### 5.2b Classe `TagChipWidget` (nuovo file `gui/tag_chip_widget.py` o inline in `main_window.py`)

```python
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QSizePolicy
from PyQt6.QtCore import Qt, pyqtSignal

class TagChipWidget(QWidget):
    """Widget compatto che mostra i tag come chip/pill cliccabili in orizzontale.
    Il layout va a capo automaticamente se ci sono troppi tag."""

    tag_clicked = pyqtSignal(str)        # emette il nome del tag cliccato ("" per reset)
    manage_requested = pyqtSignal()      # emesso al clic su [+]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_tag: str = ""
        self._chips: dict[str, QLabel] = {}
        self._build_ui()

    def _build_ui(self):
        # Layout orizzontale wrappante
        from PyQt6.QtWidgets import QFlowLayout  # vedi nota sotto
        self._flow = FlowLayout(self)
        self._flow.setSpacing(4)
        self.setStyleSheet(
            "TagChipWidget {"
            "  background-color: #2a2a2a;"
            "  border: 1px solid #444;"
            "  border-radius: 6px;"
            "  padding: 4px 6px;"
            "}"
        )

        # Pulsante gestione
        self._manage_btn = QPushButton("➕")
        self._manage_btn.setFixedSize(24, 24)
        self._manage_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._manage_btn.setStyleSheet(
            "QPushButton {"
            "  background: transparent; color: #888; border: none; font-size: 14px;"
            "}"
            "QPushButton:hover { color: #fff; }"
        )
        self._manage_btn.setToolTip("Gestisci tag")
        self._manage_btn.clicked.connect(self.manage_requested.emit)

    def set_tags(self, tags: list[str]):
        """Ricostruisce i chip. `tags` è la lista ordinata di nomi tag."""
        # Rimuovi tutti i chip esistenti
        for chip in self._chips.values():
            self._flow.removeWidget(chip)
            chip.deleteLater()
        self._chips.clear()
        self._flow.removeWidget(self._manage_btn)

        # Chip "Tutti i file"
        all_chip = self._make_chip("Tutti i file", "")
        self._flow.addWidget(all_chip)

        # Chip per ogni tag
        for tag_name in tags:
            chip = self._make_chip(tag_name, tag_name)
            self._flow.addWidget(chip)

        # Pulsante gestione in fondo
        self._flow.addWidget(self._manage_btn)

        # Ripristina selezione
        self._update_styles()

    def _make_chip(self, label: str, tag_value: str) -> QLabel:
        chip = QLabel(label)
        chip.setCursor(Qt.CursorShape.PointingHandCursor)
        chip.setStyleSheet(self._chip_style(selected=False))
        chip.mousePressEvent = lambda e, tv=tag_value: self._on_chip_click(tv)
        self._chips[tag_value] = chip
        return chip

    def _chip_style(self, selected: bool) -> str:
        if selected:
            return (
                "QLabel {"
                "  color: #fff;"
                "  background-color: #555;"
                "  border-radius: 4px;"
                "  padding: 2px 8px;"
                "  font-weight: bold;"
                "}"
            )
        return (
            "QLabel {"
            "  color: #aaa;"
            "  background-color: transparent;"
            "  border-radius: 4px;"
            "  padding: 2px 8px;"
            "}"
            "QLabel:hover {"
            "  background-color: #444;"
            "}"
        )

    def _on_chip_click(self, tag_value: str):
        if self._selected_tag == tag_value:
            # Clic sullo stesso tag → deseleziona (torna a "Tutti i file")
            self._selected_tag = ""
            self.tag_clicked.emit("")
        else:
            self._selected_tag = tag_value
            self.tag_clicked.emit(tag_value)
        self._update_styles()

    def _update_styles(self):
        for tag_value, chip in self._chips.items():
            chip.setStyleSheet(self._chip_style(selected=(tag_value == self._selected_tag)))


# ─── FlowLayout: layout orizzontale che va a capo automaticamente ───
# Qt non ha un flow layout nativo. Ecco una implementazione minima:

from PyQt6.QtCore import QRect, QSize, QPoint

class FlowLayout(QHBoxLayout):
    """Layout orizzontale che wrappa i widget su più righe."""
    # Nota: per semplicità si può usare un approccio più semplice:
    # un QWidget con word-wrap usando una QLabel HTML, oppure
    # un'implementazione completa di FlowLayout (vedi Qt docs).
    # In alternativa, usare un QHBoxLayout annidato dentro un QScrollArea
    # con scroll orizzontale se troppi tag.
    #
    # Per l'implementazione effettiva: usare il FlowLayout ufficiale
    # dagli esempi Qt (https://doc.qt.io/qt-6/qtwidgets-layouts-flowlayout-example.html)
    # oppure questa versione semplificata:

    def __init__(self, parent=None, margin=0, spacing=-1):
        super().__init__(parent)
        self._items = []
        self._h_spacing = spacing if spacing >= 0 else 4
        self._v_spacing = 4
        if margin >= 0:
            self.setContentsMargins(margin, margin, margin, margin)

    def addWidget(self, w):
        super().addWidget(w)

    # Per una vera flow, usa l'implementazione completa dagli esempi Qt.
    # Qui assumiamo che i tag siano pochi (≤10) e stiano su 1-2 righe.
```

**Nota implementativa**: Qt non ha un flow layout nativo. Le opzioni sono:
1. **FlowLayout ufficiale Qt** (dagli esempi Qt Widgets) — implementazione completa, 150 righe
2. **QLabel con HTML** — tutti i tag in una stringa HTML con `<a>` cliccabili, ma styling limitato
3. **QHBoxLayout semplice** — se i tag sono ≤8 stanno su una riga; con scroll orizzontale se overflow

**Raccomandazione**: usare l'opzione 3 (QHBoxLayout + QScrollArea) per semplicità. Se in futuro servono più tag, migrare al FlowLayout ufficiale.

#### 5.3 Nuovi attributi e metodi

```python
# In __init__:
self._current_tag_filter: str = ""  # "" = nessun filtro (mostra tutti)
self._tag_delegate = TagDelegate()

# In _build_ui(), dopo la creazione di cloud_table:
self.cloud_table.setItemDelegateForColumn(5, self._tag_delegate)
self.cloud_table.model().dataChanged.connect(self._on_tag_cell_changed)

# In _connect_signals():
self.tag_chip_widget.tag_clicked.connect(self._on_tag_chip_clicked)
self.tag_chip_widget.manage_requested.connect(self._on_open_tags_settings)
```

#### 5.4 Handler: selezione tag (chip)

```python
def _on_tag_chip_clicked(self, tag_name: str):
    """Quando l'utente clicca un chip tag, filtra i file."""
    self._current_tag_filter = tag_name
    if tag_name == "":
        # Mostra tutti
        self._refresh_file_list()
    else:
        # Filtra per tag (cross-channel, rispetta channel_filter)
        records = self.db.get_files_by_tag(tag_name, self._channel_filter)
        self.cloud_model.set_files(records)
        self.status_bar.showMessage(
            f"{len(records)} file con tag '{tag_name}'"
        )

def _load_tag_list(self):
    """Popola il TagChipWidget e il drop_tag_combo con i tag disponibili."""
    tags = self.db.get_tags()
    tag_names = [t['tag_name'] for t in tags]

    # Aggiorna il widget chip
    self.tag_chip_widget.set_tags(tag_names)

    # Aggiorna il delegate per la colonna Tags
    self._tag_delegate.set_tags(tag_names)

    # Aggiorna il combo nel drop area
    self.drop_tag_combo.clear()
    self.drop_tag_combo.addItem("🏷️ Nessun tag", "")
    for t in tags:
        self.drop_tag_combo.addItem(f"🏷️ {t['tag_name']}", t['tag_name'])

def _on_tag_cell_changed(self, top_left, bottom_right):
    """Quando l'utente modifica il tag nella cella della tabella."""
    if top_left.column() != 5:
        return
    for row in range(top_left.row(), bottom_right.row() + 1):
        index = self.cloud_model.index(row, 5)
        file = self.cloud_model.get_file(index)
        if file and file.message_id > 0:
            new_tag = file.tags
            self.db.update_file_tag(file.message_id, new_tag)
    # Ricarica se stiamo filtrando per un tag che è stato modificato
    if self._current_tag_filter:
        self._on_tag_chip_clicked(self._current_tag_filter)

def _on_open_tags_settings(self):
    """Apre il tab Tags nel dialog impostazioni."""
    self._open_settings_dialog(initial_tab=SettingsDialog.TAB_TAGS)

def _update_tag_list_for_filter(self):
    """Quando cambia il filtro canale, aggiorna anche il filtro tag se attivo."""
    if self._current_tag_filter:
        records = self.db.get_files_by_tag(self._current_tag_filter, self._channel_filter)
        self.cloud_model.set_files(records)
```

#### 5.5 Upload con tag

Aggiungere un selettore di tag vicino ai controlli di upload/drop:

```python
# In _build_ui(), nei drop_controls (colonna sinistra), aggiungere:
self.drop_tag_combo = QComboBox()
self.drop_tag_combo.setMinimumWidth(140)
self.drop_tag_combo.setToolTip("Tag da assegnare ai file uploadati via drop")
self.drop_tag_combo.addItem("🏷️ Nessun tag", "")
drop_controls.addWidget(QLabel("Tag:"))
drop_controls.addWidget(self.drop_tag_combo)

# Aggiornare _load_tag_list() per popolare anche drop_tag_combo:
def _load_tag_list(self):
    # ... (codice sopra) ...
    # Aggiorna anche il combo nel drop area
    self.drop_tag_combo.clear()
    self.drop_tag_combo.addItem("🏷️ Nessun tag", "")
    tags = self.db.get_tags()
    for t in tags:
        self.drop_tag_combo.addItem(f"🏷️ {t['tag_name']}", t['tag_name'])
    self._tag_delegate.set_tags([t['tag_name'] for t in tags])
```

Modificare `_on_drop_files_upload()` e `_upload_paths()` per passare il tag:

```python
def _on_drop_files_upload(self, paths: list):
    ch_id = self._drop_upload_channel_id or self.channel_id
    if not ch_id:
        QMessageBox.warning(self, "Errore", "Configura prima un canale Telegram")
        return
    tag = self.drop_tag_combo.currentData() or ""
    self.status_bar.showMessage(f"Upload di {len(paths)} file in coda...")
    for path in paths:
        op_id = self.transfer_manager.add_upload(ch_id, path)
        # Salviamo il tag nell'operazione? O lo applichiamo al completamento?
        # Vedi sezione 6.
    self.transfer_dialog.show()
```

#### 5.6 Inizializzazione

In `__init__`, dopo `_load_favorite_channels()`:

```python
self._load_tag_list()
```

In `_on_settings_applied()`:

```python
def _on_settings_applied(self, config: dict):
    self.config = config
    self._load_favorite_channels()
    self._load_tag_list()  # ← aggiunto
    self._refresh_cloud()
```

---

### 6. Flusso Upload con Tag

Il tag va propagato attraverso tutta la catena upload: UI → transfer_manager → telegram_client → cloud_model → database.

#### 6.1 Opzione A: Tag nell'operazione TransferOp

Aggiungere `tag: str = ""` al dataclass `TransferOp` in `transfer_manager.py`:

```python
@dataclass
class TransferOp:
    op_id: str
    op_type: str
    channel_id: int
    file_path: str = ""
    message_id: int = 0
    filename: str = ""
    status: str = "queued"
    progress: int = 0
    total: int = 0
    error_msg: str = ""
    tag: str = ""  # ← NUOVO
```

Modificare `add_upload()`:

```python
def add_upload(self, channel_id: int, file_path: str, tag: str = "") -> str:
    op_id = str(uuid.uuid4())[:8]
    op = TransferOp(
        op_id=op_id,
        op_type="upload",
        channel_id=channel_id,
        file_path=file_path,
        filename=Path(file_path).name,
        tag=tag,
    )
    # ... resto invariato
```

#### 6.2 Opzione B: Salvare tag nell'operazione e scrivere su DB al completamento

Quando l'upload viene completato (`_on_transfer_done` in `MainWindow`), usare il tag dal `TransferOp`:

```python
def _on_transfer_done(self, op_id: str, op_type: str, success: bool, msg: str, filename: str):
    self.cloud_model.remove_transfer(op_id)
    if success:
        self._notify_transfer_done(op_type, filename)
        # Applica il tag se presente
        op = self.transfer_manager.get_op_by_id(op_id)  # nuovo metodo
        if op and op.tag:
            self.db.update_file_tag_by_filename(filename, op.tag)  # nuovo metodo
    if success and op_type == "upload":
        self._refresh_cloud()
    if success:
        self._refresh_local_tree()
```

**Problema**: `message_id` non è noto al momento del `transfer_done` — viene assegnato da Telegram. Durante `_refresh_cloud()` (che chiama `list_files`), il `message_id` viene ottenuto. Il tag va applicato **dopo** `list_files`, durante `_on_file_list_ready()`.

#### 6.3 Soluzione: Coda di tag pendenti

```python
# In MainWindow.__init__:
self._pending_tags: Dict[str, str] = {}  # filename → tag

# In _on_drop_files_upload / _upload_paths:
tag = self.drop_tag_combo.currentData() or ""
for path in paths:
    op_id = self.transfer_manager.add_upload(ch_id, path)
    if tag:
        self._pending_tags[Path(path).name] = tag

# In _on_file_list_ready (dopo insert_file):
def _on_file_list_ready(self, files: list):
    for f in files:
        self.db.insert_file(
            message_id=f["message_id"],
            filename=f["filename"],
            size=f.get("size", 0),
            mime_type=f.get("mime_type", ""),
            tags=self._pending_tags.pop(f["filename"], ""),  # ← applica tag pendente
            channel_id=self.channel_id,
        )
    self._refresh_file_list()
```

**Vantaggio**: Semplice, nessuna modifica a `TransferOp` o `transfer_manager`. Il tag viene applicato quando il file viene registrato nel DB locale dopo il refresh.

---

### 7. Nuovo Tab "Tags" nelle Impostazioni (`gui/settings_dialog.py`)

#### 7.1 Classe `TagsTab`

Analoga a `FavoriteChannelsTab`, ma più semplice (nessuna lista "tutti i canali" — i tag si creano liberamente):

```python
class TagsTab(QWidget):
    """Tab per gestire i tag all'interno del SettingsDialog."""

    tags_changed = pyqtSignal()

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self._tags: List[Dict] = []
        self._build_ui()
        self._load_tags()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        # Input per nuovo tag
        input_layout = QHBoxLayout()
        self.new_tag_edit = QLineEdit()
        self.new_tag_edit.setPlaceholderText("Nome del nuovo tag...")
        self.new_tag_edit.returnPressed.connect(self._on_add_tag)
        input_layout.addWidget(self.new_tag_edit, stretch=1)
        self.btn_add = QPushButton("➕ Aggiungi")
        self.btn_add.clicked.connect(self._on_add_tag)
        input_layout.addWidget(self.btn_add)
        layout.addLayout(input_layout)

        # Lista tag con controlli
        group = QGroupBox("🏷️ Tag Disponibili")
        group_layout = QVBoxLayout(group)

        self.tag_list = QListWidget()
        self.tag_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.tag_list.itemDoubleClicked.connect(self._on_rename_tag)
        group_layout.addWidget(self.tag_list)

        btn_layout = QHBoxLayout()
        self.btn_rename = QPushButton("✏️ Rinomina")
        self.btn_rename.clicked.connect(self._on_rename_tag)
        self.btn_remove = QPushButton("➖ Rimuovi")
        self.btn_remove.clicked.connect(self._on_remove_tag)
        self.btn_up = QPushButton("⬆ Su")
        self.btn_up.clicked.connect(self._on_move_up)
        self.btn_down = QPushButton("⬇ Giù")
        self.btn_down.clicked.connect(self._on_move_down)
        btn_layout.addWidget(self.btn_rename)
        btn_layout.addWidget(self.btn_remove)
        btn_layout.addWidget(self.btn_up)
        btn_layout.addWidget(self.btn_down)
        btn_layout.addStretch()
        group_layout.addLayout(btn_layout)

        layout.addWidget(group)

        # Info conteggio
        self.info_label = QLabel("")
        self.info_label.setStyleSheet("color: #888; font-style: italic;")
        layout.addWidget(self.info_label)
        layout.addStretch()

    def _load_tags(self):
        self._tags = self.db.get_tags()
        self._refresh_list()

    def _refresh_list(self):
        self.tag_list.clear()
        for t in self._tags:
            # Conta quanti file usano questo tag
            count = len(self.db.get_files_by_tag(t['tag_name']))
            display = f"{t['tag_name']} ({count} file)"
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, t)
            self.tag_list.addItem(item)
        self.info_label.setText(f"{len(self._tags)} tag disponibili")

    def _on_add_tag(self):
        name = self.new_tag_edit.text().strip()
        if not name:
            return
        # Verifica duplicati
        if any(t['tag_name'].lower() == name.lower() for t in self._tags):
            QMessageBox.warning(self, "Attenzione", f"Il tag '{name}' esiste già.")
            return
        new_tag = {
            "tag_id": -1,  # placeholder
            "tag_name": name,
            "sort_order": len(self._tags),
        }
        self._tags.append(new_tag)
        self._refresh_list()
        self.new_tag_edit.clear()
        self.tags_changed.emit()

    def _on_remove_tag(self):
        item = self.tag_list.currentItem()
        if not item:
            return
        idx = self.tag_list.row(item)
        tag = self._tags[idx]
        # Verifica se ci sono file con questo tag
        count = len(self.db.get_files_by_tag(tag['tag_name']))
        if count > 0:
            reply = QMessageBox.question(
                self, "Conferma",
                f"Il tag '{tag['tag_name']}' è usato da {count} file.\n"
                f"Rimuovendolo, il tag verrà rimosso da tutti i file.\nContinuare?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self._tags.pop(idx)
        for i, t in enumerate(self._tags):
            t['sort_order'] = i
        self._refresh_list()
        self.tags_changed.emit()

    def _on_rename_tag(self):
        item = self.tag_list.currentItem()
        if not item:
            return
        idx = self.tag_list.row(item)
        tag = self._tags[idx]
        from PyQt6.QtWidgets import QInputDialog
        new_name, ok = QInputDialog.getText(
            self, "Rinomina tag", "Nuovo nome del tag:", text=tag['tag_name']
        )
        if ok and new_name.strip() and new_name.strip() != tag['tag_name']:
            new_name = new_name.strip()
            if any(t['tag_name'].lower() == new_name.lower() for t in self._tags):
                QMessageBox.warning(self, "Attenzione", f"Il tag '{new_name}' esiste già.")
                return
            # Aggiorna il nome nel DB (e nei file)
            # Nota: il salvataggio effettivo avviene in save_to_db()
            tag['tag_name'] = new_name
            self._refresh_list()
            self.tags_changed.emit()

    def _on_move_up(self):
        idx = self.tag_list.currentRow()
        if idx <= 0:
            return
        self._tags[idx], self._tags[idx - 1] = self._tags[idx - 1], self._tags[idx]
        for i, t in enumerate(self._tags):
            t['sort_order'] = i
        self._refresh_list()
        self.tag_list.setCurrentRow(idx - 1)
        self.tags_changed.emit()

    def _on_move_down(self):
        idx = self.tag_list.currentRow()
        if idx < 0 or idx >= len(self._tags) - 1:
            return
        self._tags[idx], self._tags[idx + 1] = self._tags[idx + 1], self._tags[idx]
        for i, t in enumerate(self._tags):
            t['sort_order'] = i
        self._refresh_list()
        self.tag_list.setCurrentRow(idx + 1)
        self.tags_changed.emit()

    def get_tags(self) -> List[Dict]:
        return self._tags

    def save_to_db(self):
        """Salva tutti i tag nel DB. Gestisce rinomine e nuove aggiunte."""
        # Ottieni i tag esistenti per gestire le rinomine
        existing = {t['tag_name']: t for t in self.db.get_tags()}
        new_names = {t['tag_name'] for t in self._tags}

        # Per ogni tag esistente che è stato rinominato, aggiorna i file
        for old_name, old_tag in existing.items():
            if old_name not in new_names:
                # Il tag è stato rimosso — gestito da remove_tag individuale
                pass

        # Rinomina: trova match per tag_id
        for new_tag in self._tags:
            if new_tag['tag_id'] > 0:
                for old_name, old_tag in existing.items():
                    if old_tag['tag_id'] == new_tag['tag_id'] and old_name != new_tag['tag_name']:
                        self.db.rename_tag(new_tag['tag_id'], new_tag['tag_name'])
                        break

        # Sovrascrivi la tabella tags
        self.db.set_tags(self._tags)
```

#### 7.2 Integrazione in `SettingsDialog`

```python
# Nuova costante:
TAB_TAGS = 3

# In __init__:
self._initial_tab = initial_tab

# In _build_ui():
self.tab_tags = TagsTab(self.db)
self.tabs.addTab(self.tab_tags, "🏷️ Tags")

# In _on_save():
self.tab_tags.save_to_db()
```

---

### 8. Riepilogo dei File Modificati

| File | Tipo modifica | Descrizione |
|---|---|---|
| `database.py` | ✏️ Modifica | Nuovi metodi: `get_tags`, `add_tag`, `remove_tag`, `rename_tag`, `update_file_tag`, `set_tags`, `get_files_by_tag`. Nuova tabella `tags` in `_init_db()`. |
| `gui/cloud_model.py` | ✏️ Modifica | `flags()` rende colonna 5 editabile. Aggiunto `setData()`. Nuova classe `TagDelegate`. |
| `gui/main_window.py` | ✏️ Modifica | `TagChipWidget` (chip/pill compatti orizzontali) sotto cloud_table. Tag combo nei drop controls. Handler `_on_tag_chip_clicked`, `_load_tag_list`, `_on_tag_cell_changed`. Logica `_pending_tags` per upload. |
| `gui/settings_dialog.py` | ✏️ Modifica | Nuova classe `TagsTab`. Aggiunto tab "🏷️ Tags" in `SettingsDialog`. Costante `TAB_TAGS = 3`. |
| `gui/transfer_manager.py` | ❌ Nessuna | Se si usa l'approccio `_pending_tags`, non servono modifiche. |
| `gui/tag_chip_widget.py` | 🆕 Nuovo file | Classe `TagChipWidget`: widget compatto con chip/pill cliccabili, flow layout orizzontale, segnali `tag_clicked(str)` e `manage_requested()`. |

---

### 9. Flusso Utente Completo

```
1. L'utente va su Impostazioni → Tab Tags
2. Crea i tag desiderati: "lavoro", "personale", "progetti", ...
3. Torna alla finestra principale
4. Vede i chip tag sotto la tabella cloud: `Tutti i file, lavoro, personale, progetti`

UPLOAD CON TAG:
5. Seleziona file locali
6. Sceglie un tag dal combo "🏷️ Tag:" nella colonna sinistra
7. Clicca Upload o trascina sul drop area
8. Il file viene uploadato → al refresh, il tag viene salvato nel DB

MODIFICA TAG POST-UPLOAD:
9. Clicca sulla cella "Tags" di un file nella tabella cloud
10. Appare un QComboBox con tutti i tag disponibili
11. Seleziona un tag → il DB viene aggiornato immediatamente

FILTRAGGIO PER TAG:
12. Clicca sul chip "lavoro" nel box tag sotto la tabella
13. "lavoro" diventa neretto, la tabella mostra solo file con tag "lavoro" (cross-channel)
14. Clicca "Tutti i file" (o di nuovo su "lavoro") per tornare alla vista completa
```

---

### 10. Considerazioni Aggiuntive

#### 10.1 Consistenza tag dopo rinomina
Quando un tag viene rinominato, `TagsTab.save_to_db()` chiama `db.rename_tag()` che aggiorna sia la tabella `tags` che la colonna `files.tags` per tutti i file. Questo garantisce consistenza.

#### 10.2 Consistenza tag dopo eliminazione
`db.remove_tag()` resetta `files.tags = ''` per tutti i file che usavano quel tag. L'utente viene avvisato con un dialog di conferma.

#### 10.3 Performance
- `get_files_by_tag()` usa un indice sulla colonna `tags` (già esistente: `idx_tags`).
- Il `TagChipWidget` occupa solo **30-50px** di altezza (vs ~150px di un QListWidget), massimizzando lo spazio per la tabella cloud.
- La lista tag viene ricaricata solo all'avvio e dopo modifiche nelle impostazioni.
- Il flow layout va a capo automaticamente: con ≤8 tag sta su 1 riga, fino a ~15 su 2 righe.

#### 10.4 Filtri combinati
Il filtro tag è **aggiuntivo** al filtro canale: se l'utente filtra per canale "X" e clicca tag "lavoro", vengono mostrati solo i file del canale X con tag "lavoro". Il metodo `get_files_by_tag` supporta già il parametro `channel_id`.

#### 10.5 Tag e ricerca testuale
La ricerca testuale (`search_files`) già cerca nella colonna `tags`. Se l'utente cerca "lavoro", troverà sia i file con "lavoro" nel nome che quelli con tag "lavoro".

#### 10.6 Tag vuoto / Nessun tag
Il valore `""` (stringa vuota) nella colonna `tags` significa "nessun tag". Il `TagDelegate` include sempre l'opzione vuota come prima scelta. Il combo upload ha "🏷️ Nessun tag" come default.
