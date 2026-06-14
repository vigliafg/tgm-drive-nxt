@echo off
REM TGM Drive — Installer & Launcher per Windows
REM Esegui questo file dalla root del progetto (doppio clic o da terminale):
REM   scripts\install-windows.bat
REM
REM Al termine, potrai avviare l'app con il comando globale:
REM   tgm-drive
REM
REM Richiede privilegi di amministratore per creare il launcher in C:\Windows\System32\

setlocal enabledelayedexpansion

set "PROJECT_DIR=%~dp0.."
for %%i in ("%PROJECT_DIR%") do set "PROJECT_DIR=%%~fi"
set "VENV_DIR=%PROJECT_DIR%\.venv"
set "LAUNCHER_NAME=tgm-drive.bat"

echo.
echo ============================================================
echo    TGM Drive — Installer Windows
echo ============================================================
echo.

REM ── 1. Verifica Python ──────────────────────────────────────────────
echo [1/4] Verifica Python 3.10+...

where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERRORE] Python non trovato nel PATH.
    echo   Scarica Python 3.10+ da https://www.python.org/downloads/
    echo   Durante l'installazione, spunta "Add Python to PATH"
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2^>nul') do set "PY_VERSION=%%v"
if "%PY_VERSION%"=="" (
    echo [ERRORE] Impossibile determinare la versione di Python.
    pause
    exit /b 1
)

for /f "tokens=1 delims=." %%a in ("%PY_VERSION%") do set "PY_MAJOR=%%a"
for /f "tokens=2 delims=." %%a in ("%PY_VERSION%") do set "PY_MINOR=%%a"

if %PY_MAJOR% LSS 3 (
    echo [ERRORE] Python %PY_VERSION% rilevato. Richiesto Python 3.10+.
    pause
    exit /b 1
)
if %PY_MAJOR% EQU 3 if %PY_MINOR% LSS 10 (
    echo [ERRORE] Python %PY_VERSION% rilevato. Richiesto Python 3.10+.
    pause
    exit /b 1
)
echo    Python %PY_VERSION% — OK

REM ── 2. Crea virtual environment ─────────────────────────────────────
echo [2/4] Creazione virtual environment in .venv\...
python -m venv "%VENV_DIR%"
if %ERRORLEVEL% neq 0 (
    echo [ERRORE] Creazione virtual environment fallita.
    pause
    exit /b 1
)
echo    Virtual environment creato — OK

REM ── 3. Installa dipendenze ──────────────────────────────────────────
echo [3/4] Installazione dipendenze Python...
call "%VENV_DIR%\Scripts\python.exe" -m pip install --quiet --upgrade pip
call "%VENV_DIR%\Scripts\pip.exe" install --quiet -r "%PROJECT_DIR%\requirements.txt"
if %ERRORLEVEL% neq 0 (
    echo [ERRORE] Installazione dipendenze fallita.
    pause
    exit /b 1
)
echo    Dipendenze installate — OK

REM ── 4. Crea il launcher globale ─────────────────────────────────────
echo [4/4] Creazione launcher globale 'tgm-drive'...
set "LAUNCHER_PATH=%PROJECT_DIR%\scripts\%LAUNCHER_NAME%"

(
echo @echo off
echo REM TGM Drive Launcher — generato automaticamente da install-windows.bat
echo set "PROJECT_DIR=!PROJECT_DIR!"
echo set "VENV_PYTHON=!PROJECT_DIR!\.venv\Scripts\python.exe"
echo set "MAIN_SCRIPT=!PROJECT_DIR!\main.py"
echo.
echo if not exist "%%MAIN_SCRIPT%%" ^(
echo     echo [ERRORE] TGM Drive non trovato in !PROJECT_DIR!
echo     echo   Reinstalla con: cd /d !PROJECT_DIR! ^&^& scripts\install-windows.bat
echo     exit /b 1
echo ^)
echo.
echo cd /d "!PROJECT_DIR!"
echo start "" /B "%%VENV_PYTHON%%" "%%MAIN_SCRIPT%%" %%*
) > "%LAUNCHER_PATH%"

echo    Launcher creato: %LAUNCHER_PATH%

REM ── Aggiungi la cartella scripts al PATH utente ─────────────────────
echo.
echo Per usare 'tgm-drive' da qualsiasi terminale, aggiungi la cartella
echo scripts al PATH di sistema:
echo.
echo    %PROJECT_DIR%\scripts
echo.
echo   Per farlo ora (manuale):
echo     1. Apri Impostazioni di sistema ^> Sistema ^> Info ^> Impostazioni di sistema avanzate
echo     2. Clicca "Variabili d'ambiente..."
echo     3. Nella sezione "Variabili utente", seleziona "Path" e clicca "Modifica..."
echo     4. Clicca "Nuovo" e incolla:  %PROJECT_DIR%\scripts
echo     5. Clicca OK su tutte le finestre
echo.
echo   In alternativa, avvia tgm-drive direttamente con:
echo     %PROJECT_DIR%\scripts\tgm-drive
echo.

echo ============================================================
echo    Installazione completata!
echo ============================================================
echo.
echo    Dopo aver aggiunto la cartella scripts al PATH,
echo    potrai avviare TGM Drive da qualsiasi terminale con:
echo      tgm-drive
echo.
pause
