# TGM Drive ☁️

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org)
[![PyQt6](https://img.shields.io/badge/PyQt-6.4%2B-green)](https://riverbankcomputing.com/software/pyqt/)
[![License](https://img.shields.io/badge/License-GPL--3.0-orange)](LICENSE)

**Trasforma un canale Telegram privato nel tuo cloud personale.**

Applicazione desktop in **PyQt6** che trasforma uno o più canali Telegram privati in uno spazio cloud personale per l'upload e il download di file di qualsiasi tipo, con dimensione massima di **2 GB** (o **4 GB** con Telegram Premium).

---

## 📸 Screenshot

*Coming soon*

---

## ✨ Caratteristiche

### Core
- **⬆ Upload & ⬇ Download** con barra di progresso e velocità in tempo reale
- **Drag & Drop** dei file direttamente dall'explorer locale o dal file manager del sistema operativo
- **Drag & Drop** dei file cloud verso il drop box per il download immediato
- **Esploratore locale integrato** (`QFileSystemModel`) con navigazione ad albero
- **Lista file cloud** con ricerca, filtri e colonne ordinabili
- **Preview file**: testo per file testuali, placeholder per immagini e altri tipi

### Gestione Multi-Canale
- **Supporto multi-canale**: gestisci più canali Telegram come spazi cloud separati
- **⭐ Canali Preferiti**: barra rapida in alto per passare da un canale all'altro con un clic
- **📋 Copia/📦 Sposta** file tra canali con operazioni in due fasi (download → upload)
- **Filtro canale**: visualizza file di un canale specifico o di tutti i canali

### Resilienza
- **Catena Copy/Move persistente**: lo stato di ogni operazione copy/move è salvato in SQLite. Se l'app crasha, al riavvio i file temporanei vengono puliti e le operazioni interrotte vengono notificate.
- **Event-driven client Telegram**: il loop asyncio usa `asyncio.Event` invece del polling a 100ms → latenza zero, CPU idle ~0%.

### Sistema di Tag
- **🏷️ Tag singolo per file**: assegna un tag a ciascun file durante l'upload o successivamente
- **Filtro per tag cross-channel**: filtra i file per tag su tutti i canali contemporaneamente
- **Chip cliccabili**: interfaccia compatta con chip/pill sotto la tabella cloud
- **Gestione tag**: crea, rinomina, elimina, riordina i tag dalle Impostazioni

### Coda di Trasferimento
- **Coda asincrona**: upload e download in coda gestiti da `TransferManager`
- **Finestra trasferimenti**: visualizza progresso, velocità MB/s, file completati/errore
- **Auto-clear**: pulizia automatica dei trasferimenti completati
- **Badge colorati**: blu per upload, ambra per download, verde per completato, rosso per errore

### Interfaccia Utente
- **Tema Dark/Light/System** selezionabile dalle impostazioni
- **Dimensione font** regolabile (8-24 pt)
- **Wizard di primo avvio**: guida passo-passo per configurare l'app in 2 minuti
- **Notifiche di sistema**: popup + beep al completamento di ogni trasferimento
- **Barra di stato**: messaggi informativi in tempo reale
- **Scorciatoie**: `F5` per aggiornare, `Delete` per eliminare file selezionati
- **Checkbox di selezione multipla**: seleziona più file con le checkbox e applica azioni batch

### Test
- **426 test**, tutti passanti, zero flaky
- **68% coverage** complessivo, **100% sui moduli di logica pura** (`database.py`, `config.py`, `gui/services/`)
- CI via GitHub Actions con matrix Python 3.10/3.11/3.12

### Tecnologia
- **Autenticazione MTProto** tramite [Telethon](https://github.com/LonamiWebs/Telethon) (account utente, non bot)
- **Thread dedicato**: client Telegram in `QThread` separato con event loop asyncio → GUI sempre reattiva
- **Database SQLite** locale (`~/.tgm_drive/files.db`) per metadati, ricerca rapida e browsing offline
- **Sessione persistente**: il file `.session` evita di reinserire le credenziali a ogni avvio
- **Configurazione JSON**: `~/.tgm_drive/config.json` per tutte le preferenze

---

## 📋 Requisiti

- **Python 3.10** o superiore
- **PyQt6** ≥ 6.4.0 (interfaccia grafica)
- **Telethon** ≥ 1.28.0 (client MTProto Telegram)
- Sistema operativo: **Linux**, **macOS**, o **Windows**

---

## 🚀 Installazione

### Metodo Rapido (consigliato)

Usa lo script di installazione per il tuo sistema operativo. Lo script crea automaticamente l'ambiente virtuale, installa le dipendenze e configura il launcher globale **`tgm-drive`**.

#### Linux

```bash
git clone https://github.com/tuouser/tgm-drive-nxt.git
cd tgm-drive-nxt
chmod +x scripts/install-linux.sh
./scripts/install-linux.sh
```

Poi avvia l'app da qualsiasi terminale con:

```bash
tgm-drive
```

> **Nota:** Se `~/.local/bin` non è nel tuo PATH, aggiungi `export PATH="$HOME/.local/bin:$PATH"` al tuo `~/.bashrc` o `~/.zshrc`.

#### macOS

```bash
git clone https://github.com/tuouser/tgm-drive-nxt.git
cd tgm-drive-nxt
chmod +x scripts/install-macos.sh
./scripts/install-macos.sh
```

Poi avvia l'app da qualsiasi terminale con:

```bash
tgm-drive
```

#### Windows

Apri **PowerShell** o **Prompt dei comandi** nella cartella del progetto e lancia:

```cmd
scripts\install-windows.bat
```

Aggiungi la cartella `scripts\` al PATH di sistema (le istruzioni appaiono al termine dell'installazione), poi avvia l'app con:

```cmd
tgm-drive
```

### Metodo Manuale (sviluppatori)

```bash
git clone https://github.com/tuouser/tgm-drive-nxt.git
cd tgm-drive-nxt
python3 -m venv .venv
source .venv/bin/activate   # Linux/macOS
# oppure
.venv\Scripts\activate     # Windows
pip install -r requirements.txt
python main.py
```

Al primo avvio, il **Wizard di configurazione** ti guiderà nell'inserimento delle credenziali e nella scelta del canale cloud.

---

## ⚙️ Configurazione

### 1. Ottieni API ID e API Hash

1. Vai su [my.telegram.org](https://my.telegram.org)
2. Accedi con il tuo numero di telefono
3. Clicca su **"API development tools"**
4. Crea una nuova app (nome a piacere, es. "TGM Drive")
5. Annota **API ID** (numero) e **API Hash** (stringa alfanumerica)

> ⚠️ **Non condividere mai** API ID e API Hash con nessuno.

### 2. Crea un canale privato su Telegram

1. Apri Telegram (mobile o desktop)
2. Crea un **nuovo canale privato** (devi essere amministratore)
3. Ottieni l'**ID numerico** del canale:
   - Puoi selezionarlo direttamente dal wizard tramite la lista dei tuoi canali
   - Oppure usa l'ID manuale (es. `-1001234567890`)

### 3. Wizard di primo avvio

Il wizard ti accompagna in 5 semplici passi:

| Passo | Descrizione |
|-------|-------------|
| **Benvenuto** | Introduzione e prerequisiti |
| **Credenziali** | Inserimento API ID, API Hash, numero telefono |
| **Verifica** | Codice OTP ricevuto su Telegram |
| **Canale** | Selezione del canale cloud dalla lista o creazione di uno nuovo |
| **Preferiti** | Configurazione rapida canali preferiti e cartella download |

Tutte le impostazioni possono essere modificate successivamente dal menu **⚙️ Impostazioni**.

---

## 📖 Utilizzo

### Azioni principali

| Azione | Come fare |
|--------|-----------|
| **Upload** | Seleziona file dall'explorer locale e clicca **⬆ Upload**, oppure trascina i file nella **Drop Area** |
| **Download** | Seleziona un file dal cloud e clicca **⬇ Download**, oppure fai **doppio click** sul file, oppure trascina i file cloud nella Drop Area |
| **Elimina** | Seleziona i file con le checkbox e clicca **☑ Cancella selezionati**, oppure premi **Delete** |
| **Copia canale** | Seleziona i file, clicca **📋 Copia selezionati**, scegli il canale di destinazione |
| **Sposta canale** | Seleziona i file, clicca **📦 Sposta selezionati**, scegli il canale di destinazione |
| **Ricerca** | Scrivi nella barra di ricerca e premi **Invio** (ricerca per sottostringa) |
| **Aggiorna** | Premi **F5** o clicca **🔄 Aggiorna** |
| **Cambia canale** | Clicca un canale nella **⭐ barra preferiti** in alto |
| **Filtra per tag** | Clicca un chip tag sotto la tabella cloud (es. "lavoro", "personale") |
| **Assegna tag** | Clicca sulla cella "Tags" di un file nella tabella e scegli il tag dal menu a tendina |
| **Cartella Download** | Clicca **📂 Cartella Download** per scegliere dove salvare i file scaricati |

### Trascinamento (Drag & Drop)

La **Drop Area** al centro-sinistra accetta:
- **File dal filesystem** → vengono caricati in upload sul canale selezionato
- **File dalla tabella cloud** → vengono scaricati nella cartella selezionata

La Drop Area mostra un feedback visivo:
- **Bordo verde** = upload in arrivo
- **Bordo blu** = download in arrivo

### Tag

1. Vai su **⚙️ Impostazioni → 🏷️ Tags** per creare i tuoi tag (es. "lavoro", "personale", "progetti")
2. Durante l'upload, scegli il tag dal menu a tendina "Tag:" nella colonna sinistra
3. Dopo l'upload, modifica il tag cliccando sulla cella "Tags" nella tabella cloud
4. Filtra i file cliccando sui chip tag sotto la tabella (filtro cross-channel)

### Trasferimenti

La finestra **📦 Trasferimenti** mostra:
- Lista di tutti gli upload/download in corso e in coda
- Barra di progresso con percentuale
- Velocità in MB/s e dimensione totale
- Badge colorati per stato (⚡ in corso, ✅ completato, ❌ errore)
- Checkbox "🧹 Pulisci completati automaticamente"

---

## 🗂️ Struttura del Progetto

```
.
├── main.py                    # Punto di ingresso, gestione OTP, avvio MainWindow
├── config.py                  # Gestione configurazione JSON (~/.tgm_drive/config.json)
├── database.py                # Database SQLite: CRUD, ricerca, tag, canali, transfer_chains
├── telegram_client.py         # Client MTProto (Telethon) in QThread dedicato, event-driven
├── requirements.txt           # Dipendenze Python
├── requirements-test.txt      # Dipendenze per test (pytest, pytest-qt, pytest-cov)
├── README.md                  # Questo file
├── PROJECT_CONTEXT.md         # Contesto completo del progetto per sviluppatori
├── TAG_SYSTEM_DESIGN.md       # Documento di progettazione del sistema di tagging
├── TRANSFER_CHAIN_DESIGN.md   # Documento di progettazione catena copy/move persistente
├── GO_REFACTOR_DESIGN.md      # Studio di fattibilità refactoring Python → Go
├── FYNE_COMPROMISE.md         # Analisi compromessi GUI Fyne vs PyQt6
├── .github/workflows/
│   └── pytest.yml             # CI: test automatici su push/PR (matrix Python 3.10/11/12)
├── scripts/
│   ├── install-linux.sh       # Installer & launcher per Linux
│   ├── install-macos.sh       # Installer & launcher per macOS
│   ├── install-windows.bat    # Installer & launcher per Windows
│   ├── build-linux.sh         # Build eseguibile standalone (Linux)
│   ├── build-macos.sh         # Build eseguibile standalone (macOS)
│   └── build-windows.ps1      # Build eseguibile standalone (Windows)
├── tests/
│   ├── conftest.py            # Fixture condivise (DB, mock, QApplication)
│   ├── unit/
│   │   ├── test_config.py     # 11 test — load/save/merge config
│   │   ├── test_database.py   # 56 test — CRUD, search, tag, migrations, transfer_chains
│   │   ├── test_cloud_model.py           # 37 test
│   │   ├── test_transfer_manager.py      # 24 test
│   │   ├── test_transfer_chain_service.py # 43 test — catena copy/move persistente
│   │   ├── test_file_service.py          # 28 test — extract_original_filename
│   │   └── test_tag_service.py           # 22 test — PendingTagManager
│   └── ui/
│       ├── test_auth_dialog.py          # 15 test
│       ├── test_channel_dialog.py       # 35 test
│       ├── test_destination_dialog.py   # 18 test
│       ├── test_settings_dialog.py      # 68 test
│       ├── test_tag_chip_widget.py      # 27 test
│       └── test_transfer_dialog.py      # 28 test
└── gui/
    ├── __init__.py
    ├── services/
    │   ├── __init__.py
    │   ├── file_service.py            # extract_original_filename (puro, testabile)
    │   ├── tag_service.py             # PendingTagManager (puro, testabile)
    │   └── transfer_chain_service.py  # Catena copy/move persistente SQLite
    ├── auth_dialog.py         # Dialogo autenticazione iniziale (API ID, Hash, Phone)
    ├── channel_dialog.py      # Dialogo selezione canale Telegram con ricerca
    ├── main_window.py         # Finestra principale: explorer, tabella cloud, drop, tag
    ├── cloud_model.py         # Modello Qt (QAbstractTableModel) per la lista file cloud
    ├── transfer_manager.py    # Gestione coda asincrona upload/download con velocità
    ├── transfer_dialog.py     # Finestra dialog per code di trasferimento e progresso
    ├── setup_wizard.py        # Wizard di primo avvio (5 pagine guidate)
    ├── settings_dialog.py     # Impostazioni: UI, Telegram, Canali Preferiti, Tags
    ├── destination_dialog.py  # Dialogo selezione canale destinazione per copia/sposta
    └── tag_chip_widget.py     # Widget compatto chip/pill per filtraggio tag
```

---

## 🔧 Troubleshooting

### `ImportError: cannot import name 'QFileSystemModel'`

In alcune distribuzioni Linux `QFileSystemModel` si trova in `PyQt6.QtGui` invece che `QtWidgets`. Il codice è già compatibile, ma assicurati di avere **PyQt6 ≥ 6.4.0**:

```bash
pip install --upgrade PyQt6
```

### Il client Telegram non si connette

- Verifica che **API ID** e **API Hash** siano corretti
- Verifica che il **numero di telefono** sia in formato internazionale (`+39...` per l'Italia)
- Controlla la connessione internet
- Se hai cambiato password o attivato 2FA, rimuovi la sessione e riavvia:
  ```bash    rm ~/.tgm_drive/tgm_drive.session
  tgm-drive
  ```

### File troppo grandi

| Account | Limite dimensione file |
|---------|----------------------|
| Telegram Standard | **2 GB** |
| Telegram Premium | **4 GB** |

Per file più grandi, considera di comprimerli o dividerli prima dell'upload.

### Canale non trovato

- Assicurati di essere **amministratore** del canale
- Usa l'ID numerico completo con il prefisso `-100`
- Esempio: se l'ID è `1234567890`, inserisci `-1001234567890`
- In alternativa, crea un nuovo canale direttamente dall'app (pulsante "➕ Crea nuovo canale" nel wizard o nel dialog canali)

### Problemi di performance con molti file

- Il treeview locale potrebbe essere lento con cartelle contenenti migliaia di file. Usa `QFileSystemModel` con lazy loading.
- La tabella cloud carica tutti i metadati dal DB locale. Con migliaia di file, il refresh potrebbe richiedere qualche secondo.
- Per cartelle molto grandi, naviga in sottocartelle più piccole.

### Errore "database is locked"

Il client Telegram ha un retry automatico (fino a 3 tentativi) per questo errore SQLite. Se persiste:

```bash
rm ~/.tgm_drive/files.db
```

Il database verrà ricreato al prossimo avvio (i metadati saranno ripopolati al refresh).

---

## 🔒 Note sulla Sicurezza

- **File `.session`**: Il file `~/.tgm_drive/tgm_drive.session` contiene la tua sessione Telegram autenticata. **Non condividerlo mai** e assicurati che sia nel `.gitignore`.
- **API credentials**: API ID e API Hash sono salvati in `~/.tgm_drive/config.json` in chiaro. Non condividere questo file.
- **Canale privato**: Usa sempre un canale **privato** per evitare accessi indesiderati ai tuoi file.
- **Termini di Servizio**: Non usare l'app per violare i [Termini di Servizio di Telegram](https://telegram.org/tos).
- **Nessuna crittografia aggiuntiva**: I file sono trasferiti via MTProto (crittografato), ma non vengono cifrati lato client prima dell'upload. Per dati sensibili, usa strumenti di cifratura aggiuntivi.

---

## 🛠️ Sviluppo

### Quale script usare?

I due gruppi di script servono a scenari **diversi** — non vanno eseguiti in sequenza.

| | `scripts/install-*` | `scripts/build-*` |
|---|---|---|
| **A chi serve** | Sviluppatore / utente con Python | Developer che distribuisce l'app |
| **Cosa produce** | Launcher globale `tgm-drive` | Eseguibile standalone in `dist/` |
| **Richiede Python installato?** | Sì | Solo durante la build, non per l'utente finale |
| **L'utente esegue** | `tgm-drive` da terminale | `./TGM-Drive` (doppio click su Windows) |
| **Output** | `.venv/` + launcher in `~/.local/bin/` | `dist/TGM-Drive` (~40-80 MB, one-file) |

> **Regola**: se vuoi sviluppare o contribuire → `install-*`. Se vuoi distribuire un `.exe` a utenti senza Python → `build-*`.

### Setup ambiente di sviluppo

```bash
git clone https://github.com/tuouser/tgm-drive-nxt.git
cd tgm-drive-nxt
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Avvio rapido (sviluppo)

```bash
source .venv/bin/activate  # solo la prima volta
python main.py
```

### Test

```bash
source .venv/bin/activate
pip install -r requirements-test.txt

# Tutti i test
python -m pytest tests/

# Con coverage
python -m pytest tests/ --cov=. --cov-report=term-missing
```

### Documentazione per sviluppatori

- **[PROJECT_CONTEXT.md](PROJECT_CONTEXT.md)**: architettura, file structure, feature implementate, bug noti, comandi rapidi
- **[TAG_SYSTEM_DESIGN.md](TAG_SYSTEM_DESIGN.md)**: progettazione dettagliata del sistema di tagging
- **[TRANSFER_CHAIN_DESIGN.md](TRANSFER_CHAIN_DESIGN.md)**: progettazione catena copy/move persistente SQLite
- **[GO_REFACTOR_DESIGN.md](GO_REFACTOR_DESIGN.md)**: studio di fattibilità per un refactoring Python → Go
- **[FYNE_COMPROMISE.md](FYNE_COMPROMISE.md)**: analisi dei compromessi UI usando Fyne (Go) vs PyQt6 (Python)

### Convenzioni

- **Linguaggio**: codice e commenti in inglese, UI e documentazione in italiano
- **Stile**: type hints dove utile, `dataclass` per strutture dati, `pyqtSignal` per comunicazione inter-thread
- **Threading**: il client Telegram vive in un `QThread` dedicato con event loop asyncio. La GUI comunica via segnali Qt.
- **Database**: SQLite in `~/.tgm_drive/files.db`, schema auto-migrante (`CREATE TABLE IF NOT EXISTS`, `ALTER TABLE` per nuove colonne)

### Eseguibile standalone (PyInstaller)

Puoi creare un eseguibile **one-file** che non richiede Python installato. Lo script di build:
1. Crea un virtual environment (se non esiste)
2. Installa tutte le dipendenze (`requirements.txt` + `pyinstaller`)
3. Genera l'eseguibile in `dist/`

#### Linux

```bash
chmod +x scripts/build-linux.sh
./scripts/build-linux.sh
# Output: dist/TGM-Drive
```

#### macOS

```bash
chmod +x scripts/build-macos.sh
./scripts/build-macos.sh
# Output: dist/TGM-Drive
```

> Per creare un `.app` bundle macOS, aggiungi `--windowed` al comando `pyinstaller` nello script.

#### Windows (PowerShell)

```powershell
.\scripts\build-windows.ps1
# Output: dist\TGM-Drive.exe
```

> Se PowerShell blocca l'esecuzione degli script:
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
> ```

#### Note

- L'eseguibile pesa circa **40-80 MB** (include Python, PyQt6 e Telethon)
- Il primo avvio potrebbe essere più lento (PyInstaller decomprime i file in una cartella temporanea)
- I file di configurazione e database sono sempre in `~/.tgm_drive/`
- Su Windows, l'estensione dell'eseguibile è `.exe`

---

## 📄 Licenza

**GPL-3.0** (o licenza commerciale se usi PyQt6 con licenza commerciale).

Vedi il file [LICENSE](LICENSE) per il testo completo.

---

## 🙏 Crediti

- **[Telethon](https://github.com/LonamiWebs/Telethon)** — Client MTProto Python
- **[PyQt6](https://riverbankcomputing.com/software/pyqt/)** — Framework GUI
- **[Telegram](https://telegram.org)** — Piattaforma di messaggistica

---

*Made with ❤️ for personal cloud freedom*
