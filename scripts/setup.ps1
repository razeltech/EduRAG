# First-time appliance setup. Called by Setup-EduRAG.bat (elevated).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$env:PYTHONPATH = $Root

function Write-Step($msg) { Write-Host ""; Write-Host "==> $msg" -ForegroundColor Cyan }

function Refresh-Path {
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("Path", "User")
}

function Get-Python {
    $candidates = @(
        (Join-Path $Root "runtime\venv\Scripts\python.exe"),
        (Join-Path $Root ".venv\Scripts\python.exe")
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { return $c }
    }
    return $null
}

Write-Step "Python runtime (bundled, not a user install)"
$py = Get-Python
if (-not $py) {
    Write-Host "No bundled runtime yet. Creating runtime\venv with a silent Python install..."
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw "winget is missing and there is no bundled runtime. Copy this EduRAG folder from the build PC, or install winget."
    }
    & winget install --id Python.Python.3.11 -e --silent --accept-package-agreements --accept-source-agreements
    Refresh-Path
    $sysPy = Get-Command python -ErrorAction SilentlyContinue
    if (-not $sysPy) { throw "Python silent install finished but python.exe is not on PATH. Open a new admin prompt and re-run Setup." }
    $rt = Join-Path $Root "runtime"
    New-Item -ItemType Directory -Force -Path $rt | Out-Null
    & python -m venv (Join-Path $rt "venv")
    $py = Join-Path $rt "venv\Scripts\python.exe"
}

Write-Step "Python packages"
& $py -m pip install --upgrade pip
& $py -m pip install -r (Join-Path $Root "requirements.txt")

Write-Step "Ollama (local LLM engine)"
Refresh-Path
$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollama) {
    $setup = Join-Path $env:TEMP "OllamaSetup.exe"
    Write-Host "Downloading Ollama installer..."
    Invoke-WebRequest -Uri "https://ollama.com/download/OllamaSetup.exe" -OutFile $setup
    Write-Host "Installing Ollama silently..."
    Start-Process -FilePath $setup -ArgumentList "/VERYSILENT", "/NORESTART" -Wait
    Refresh-Path
    $ollama = Get-Command ollama -ErrorAction SilentlyContinue
    if (-not $ollama) {
        throw "Ollama installed but not on PATH yet. Sign out/in or re-run Setup-EduRAG.bat."
    }
}

Write-Step "LAN firewall (port 4747, Private profile only)"
netsh advfirewall firewall delete rule name="EduRAG" | Out-Null
netsh advfirewall firewall add rule name="EduRAG" dir=in action=allow protocol=TCP localport=4747 profile=private | Out-Null

Write-Step "Demo users, English OCR, chat model"
& $py -m app setup
if ($LASTEXITCODE -ne 0) { throw "python -m app setup failed" }

Write-Host ""
Write-Host "Default logins (also clickable on the web page):" -ForegroundColor Green
Write-Host "  Admin    admin@edurag.local    admin123"
Write-Host "  Teacher  teacher@edurag.local  teacher123"
Write-Host "  Student  student@edurag.local  student123"
Write-Host ""
Write-Host "Setup complete."
