#!/usr/bin/env pwsh
#===============================================================================
# Jasper Trades — Start All Servers (PowerShell)
#===============================================================================
# Checks/installs all dependencies (Python, Node.js, pip packages, npm packages,
# Kronos-mini model from Hugging Face), configures .env files, and launches all
# three servers in separate PowerShell windows:
#
#   Frontend:  http://localhost:3000
#   Backend:   http://localhost:8000
#   Kronos:    http://localhost:8001
#
# Press Ctrl+C in THIS window to stop all servers.
#===============================================================================

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$ROOT     = Resolve-Path "."
$BACKEND  = "$ROOT\backend"
$FRONTEND = "$ROOT\frontend"
$KRONOS   = "$ROOT\kronos"

$KRONOS_API_KEY = [System.Web.Security.Membership]::GeneratePassword(32, 0)

# Colours
Write-Host @"
================================================================================
   Jasper Trades — Setup & Launcher (PowerShell)
   AI-Powered Trading Platform
================================================================================
"@ -ForegroundColor Cyan

#-------------------------------------------------------------------------------
# Helper functions
#-------------------------------------------------------------------------------
function Test-Command($cmd) {
    return (Get-Command $cmd -ErrorAction SilentlyContinue) -ne $null
}

function Write-OK($msg) { Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-WARN($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-ERR($msg) { Write-Host "[ERR] $msg" -ForegroundColor Red }
function Write-INF($msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-STEP($msg) { Write-Host "`n>> $msg" -ForegroundColor Blue }

function Start-PowerShellWindow($Title, $ScriptBlock) {
    Write-INF "Opening new PowerShell window: $Title"
    $encoded = [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($ScriptBlock))
    $psArgs  = "-NoExit -EncodedCommand $encoded"
    Start-Process powershell.exe -ArgumentList $psArgs -WindowTitle $Title
}

#-------------------------------------------------------------------------------
# 1. Prerequisites
#-------------------------------------------------------------------------------
Write-STEP "Checking prerequisites..."

# Python
if (-not (Test-Command python)) {
    Write-ERR "Python not found. Install Python 3.11+ from https://python.org/"
    exit 1
}
$pyVer = (python --version 2>&1).Trim()
Write-OK "$pyVer detected"

# Node.js
if (-not (Test-Command node)) {
    Write-ERR "Node.js not found. Install Node.js 20+ from https://nodejs.org/"
    exit 1
}
$nodeVer = (node --version 2>&1).Trim()
Write-OK "$nodeVer detected"

#-------------------------------------------------------------------------------
# 2. Python virtual environments & dependencies
#-------------------------------------------------------------------------------
function Setup-PythonVenv($Dir, $RequirementsFile, $ExtraPkgs, $InstallTorchCpu) {
    $venvDir = Join-Path $Dir ".venv"
    if (-not (Test-Path $venvDir)) {
        Write-STEP "Creating virtualenv at $venvDir"
        python -m venv $venvDir | Out-Null
        Write-OK "Virtualenv created"
    } else {
        Write-OK "Virtualenv already exists at $venvDir"
    }

    $pip = Join-Path $venvDir "Scripts\pip.exe"
    $py  = Join-Path $venvDir "Scripts\python.exe"

    Write-INF "Upgrading pip..."
    & $pip install --upgrade pip -q | Out-Null

    if (Test-Path $RequirementsFile) {
        Write-STEP "Installing Python deps from $(Split-Path $RequirementsFile -Leaf)..."
        & $pip install -r $RequirementsFile -q
        Write-OK "Installed $(Split-Path $RequirementsFile -Leaf)"
    }

    if ($ExtraPkgs) {
        foreach ($pkg in $ExtraPkgs) {
            Write-INF "Installing $pkg..."
            & $pip install $pkg -q
        }
    }

    if ($InstallTorchCpu) {
        Write-STEP "Installing PyTorch CPU (2GB RAM friendly)..."
        & $pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu -q
        & $pip install huggingface_hub safetensors -q
        Write-OK "PyTorch CPU installed"
    }

    return $py
}

# Backend
if (Test-Path "$BACKEND\requirements.txt") {
    $backendPy = Setup-PythonVenv -Dir $BACKEND `
        -RequirementsFile "$BACKEND\requirements.txt" `
        -ExtraPkgs @("fastapi","uvicorn","pydantic") `
        -InstallTorchCpu $true
} else {
    Write-WARN "No backend requirements.txt found"
    $backendPy = Join-Path (Join-Path $BACKEND ".venv") "Scripts\python.exe"
}

# Kronos
$kronosPy = $null
if (Test-Path $KRONOS) {
    if (Test-Path "$KRONOS\requirements.txt") {
        $kronosPy = Setup-PythonVenv -Dir $KRONOS `
            -RequirementsFile "$KRONOS\requirements.txt" `
            -ExtraPkgs @() `
            -InstallTorchCpu $true
    } else {
        Write-WARN "No kronos requirements.txt found"
    }
}

#-------------------------------------------------------------------------------
# 3. Frontend npm dependencies
#-------------------------------------------------------------------------------
if (Test-Path "$FRONTEND\package.json") {
    Write-STEP "Installing frontend npm dependencies..."
    cd $FRONTEND
    npm install | Out-Null
    Write-OK "Frontend npm dependencies installed"
    cd $ROOT
} else {
    Write-WARN "No frontend package.json found"
}

#-------------------------------------------------------------------------------
# 4. Download Kronos model from Hugging Face
#-------------------------------------------------------------------------------
if ($kronosPy -and (Test-Path "$KRONOS\start_kronos.py")) {
    Write-STEP "Downloading Kronos-mini model from Hugging Face (~16 MB, fits 2GB RAM)..."
    $dlScript = @'
from huggingface_hub import hf_hub_download
repo_id = "NeoQuasar/Kronos"
files = ["kronos-mini.safetensors", "kronos-mini-tokenizer.json"]
for f in files:
    try:
        p = hf_hub_download(repo_id=repo_id, filename=f)
        print(f"Downloaded {f} -> {p}")
    except Exception as e:
        print(f"Failed to download {f}: {e}")
'@
    & $kronosPy -c $dlScript
    Write-OK "Kronos model download attempted"
}

#-------------------------------------------------------------------------------
# 5. Environment files
#-------------------------------------------------------------------------------
Write-STEP "Setting up environment files..."

function Ensure-EnvFile($ExamplePath, $TargetPath, $Replacements) {
    if (-not (Test-Path $TargetPath)) {
        if (Test-Path $ExamplePath) {
            Copy-Item $ExamplePath $TargetPath
            Write-OK "Created $TargetPath"
        }
    }
    if (Test-Path $TargetPath) {
        $content = Get-Content $TargetPath -Raw
        foreach ($kv in $Replacements) {
            $key   = $kv.Key
            $value = $kv.Value
            if ($content -match "^($key\s*=\s*).*$") {
                $content = $content -replace "^($key\s*=\s*).*$", "`${1}$value"
            } else {
                $content = "`n$key=$value`n" + $content
            }
        }
        Set-Content $TargetPath $content
    }
}

# Backend .env
$backendReplacements = @{
    "KRONOS_SERVICE_URL" = "http://localhost:8001"
    "KRONOS_API_KEY"     = $KRONOS_API_KEY
    "SECRET_KEY"         = [System.Web.Security.Membership]::GeneratePassword(32, 0)
    "API_AUTH_KEY"       = "jasper_" + [System.Web.Security.Membership]::GeneratePassword(16, 0)
}
Ensure-EnvFile -ExamplePath "$BACKEND\.env.example" -TargetPath "$BACKEND\.env" -Replacements $backendReplacements

# Frontend .env
$frontendReplacements = @{
    "NEXT_PUBLIC_API_URL"     = "http://localhost:8000"
    "NEXT_PUBLIC_WS_URL"      = "ws://localhost:8000"
    "NEXT_PUBLIC_KRONOS_URL"  = "http://localhost:8001"
}
Ensure-EnvFile -ExamplePath "$FRONTEND\.env.example" -TargetPath "$FRONTEND\.env" -Replacements $frontendReplacements

# Kronos .env
$kronosReplacements = @{
    "KRONOS_SERVICE_URL" = "http://localhost:8001"
    "KRONOS_API_KEY"     = $KRONOS_API_KEY
    "KRONOS_MODEL"       = "NeoQuasar/Kronos-mini"
    "KRONOS_LOCAL_PORT"  = "8001"
}
Ensure-EnvFile -ExamplePath "$KRONOS\.env.example" -TargetPath "$KRONOS\.env" -Replacements $kronosReplacements

Write-OK "Environment files configured"
Write-INF "Kronos API key: $KRONOS_API_KEY"

#-------------------------------------------------------------------------------
# 6. Start all three servers in separate PowerShell windows
#-------------------------------------------------------------------------------
$serverPids = @()

function Cleanup {
    Write-Host "`nShutting down all servers..." -ForegroundColor Cyan
    foreach ($p in $serverPids) {
        try { Stop-Process -Id $p -Force -ErrorAction SilentlyContinue } catch {}
    }
    Write-OK "All servers stopped."
    exit
}
trap { Cleanup }

# Backend
$backendScript = @"
cd '$BACKEND'
\$env:KRONOS_SERVICE_URL='http://localhost:8001'
\$env:KRONOS_API_KEY='$KRONOS_API_KEY'
& '$backendPy' -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
"@
$p = Start-Process powershell.exe -ArgumentList "-NoExit", "-Command", $backendScript -WindowTitle "Backend (:8000)" -PassThru
$serverPids += $p.Id
Write-OK "Backend window started (PID $($p.Id))"

# Give backend a moment to start before frontend
Start-Sleep -Seconds 3

# Frontend
$frontendScript = @"
cd '$FRONTEND'
\$env:NEXT_PUBLIC_API_URL='http://localhost:8000'
\$env:NEXT_PUBLIC_WS_URL='ws://localhost:8000'
\$env:NEXT_PUBLIC_KRONOS_URL='http://localhost:8001'
npm run dev
"@
$p = Start-Process powershell.exe -ArgumentList "-NoExit", "-Command", $frontendScript -WindowTitle "Frontend (:3000)" -PassThru
$serverPids += $p.Id
Write-OK "Frontend window started (PID $($p.Id))"

# Kronos
if ($kronosPy -and (Test-Path "$KRONOS\start_kronos.py")) {
    $kronosScript = @"
cd '$KRONOS'
\$env:KRONOS_SERVICE_URL='http://localhost:8001'
\$env:KRONOS_API_KEY='$KRONOS_API_KEY'
& '$kronosPy' start_kronos.py
"@
    $p = Start-Process powershell.exe -ArgumentList "-NoExit", "-Command", $kronosScript -WindowTitle "Kronos (:8001)" -PassThru
    $serverPids += $p.Id
    Write-OK "Kronos window started (PID $($p.Id))"
}

#-------------------------------------------------------------------------------
# 7. Wait for shutdown
#-------------------------------------------------------------------------------
Write-Host @"
================================================================================
   All servers are running in separate PowerShell windows!
================================================================================
   Frontend:  http://localhost:3000
   Backend:   http://localhost:8000
   Kronos:    http://localhost:8001
================================================================================
   Press Ctrl+C in THIS window to stop all servers.
================================================================================
"@ -ForegroundColor Green

try {
    while ($true) {
        Start-Sleep -Seconds 5
        foreach ($pid in $serverPids) {
            $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
            if (-not $proc) {
                Write-WARN "Server process PID $pid has stopped unexpectedly."
            }
        }
    }
} catch {
    Cleanup
}
