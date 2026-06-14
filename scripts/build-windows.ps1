# TGM Drive — Build eseguibile standalone con PyInstaller (Windows)
# Esegui dalla root del progetto in PowerShell:
#   .\scripts\build-windows.ps1
#
# Output: dist\TGM-Drive.exe (eseguibile one-file)
#
# NOTA: Se PowerShell blocca l'esecuzione:
#   Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectDir

$VenvDir = Join-Path $ProjectDir ".venv"
$ExeName = "TGM-Drive"
$DistDir = Join-Path $ProjectDir "dist"

Write-Host "🔨 TGM Drive — Build PyInstaller (Windows)" -ForegroundColor Cyan
Write-Host ""

# ── 1. Setup ambiente ──────────────────────────────────────────────────
Write-Host "[1/4] Setup ambiente..." -ForegroundColor Yellow
if (-not (Test-Path $VenvDir)) {
    Write-Host "   Creazione virtual environment..."
    python -m venv $VenvDir
}
$Activate = Join-Path $VenvDir "Scripts\Activate.ps1"
. $Activate
Write-Host "   ✅ Ambiente attivo" -ForegroundColor Green

# ── 2. Installa dipendenze ─────────────────────────────────────────────
Write-Host "[2/4] Installazione dipendenze..." -ForegroundColor Yellow
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
pip install --quiet pyinstaller
Write-Host "   ✅ Dipendenze installate" -ForegroundColor Green

# ── 3. Pulizia build precedenti ────────────────────────────────────────
Write-Host "[3/4] Pulizia build precedenti..." -ForegroundColor Yellow
if (Test-Path build) { Remove-Item -Recurse -Force build }
if (Test-Path dist)  { Remove-Item -Recurse -Force dist }
if (Test-Path *.spec) { Remove-Item -Force *.spec }
Write-Host "   ✅ Pulito" -ForegroundColor Green

# ── 4. Build con PyInstaller ───────────────────────────────────────────
Write-Host "[4/4] Build eseguibile one-file..." -ForegroundColor Yellow
Write-Host "   ⏳ Questo potrebbe richiedere 1-2 minuti..."
Write-Host ""

pyinstaller `
    --onefile `
    --name "$ExeName" `
    --add-data "README.md;." `
    --hidden-import PyQt6 `
    --hidden-import PyQt6.QtCore `
    --hidden-import PyQt6.QtGui `
    --hidden-import PyQt6.QtWidgets `
    --hidden-import telethon `
    --hidden-import telethon.tl.types `
    --hidden-import telethon.tl.functions.channels `
    --collect-all telethon `
    --noconfirm `
    main.py

Write-Host ""

# ── Verifica ───────────────────────────────────────────────────────────
$ExePath = Join-Path $DistDir "$ExeName.exe"
if (Test-Path $ExePath) {
    $Size = "{0:N0} MB" -f ((Get-Item $ExePath).Length / 1MB)
    Write-Host "✅ Build completato!" -ForegroundColor Green
    Write-Host "   Eseguibile: $ExePath" -ForegroundColor White
    Write-Host "   Dimensione: $Size" -ForegroundColor White
    Write-Host ""
    Write-Host "   Per eseguirlo: .\dist\$ExeName.exe" -ForegroundColor White
} else {
    Write-Host "❌ Build fallito. Controlla gli errori sopra." -ForegroundColor Red
    exit 1
}
