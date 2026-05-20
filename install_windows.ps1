$ErrorActionPreference = "Stop"

Write-Host "SO-101 Upma Robot Windows setup"

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    Write-Host "Python launcher 'py' was not found. Install Python 3.11 first:"
    Write-Host "https://www.python.org/downloads/windows/"
    exit 1
}

if (-not (Test-Path ".venv")) {
    py -3.11 -m venv .venv
}

.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\pip.exe install -r requirements.txt
.\.venv\Scripts\pip.exe install -e . --no-build-isolation

if (-not (Test-Path "config.json")) {
    Copy-Item "config.example.json" "config.json"
    Write-Host "Created config.json from config.example.json."
    Write-Host "Edit config.json and set robot_port to COM7 or your actual robot port."
}

Write-Host ""
Write-Host "Setup complete."
Write-Host "Next commands:"
Write-Host "  mode"
Write-Host "  .\.venv\Scripts\activate"
Write-Host "  pbl --help"
Write-Host "  pbl setup --port COM7 --cameras 1 2"
Write-Host "  pbl setup --port COM7 --leader-port COM8 --cameras 1 2"
Write-Host "  pbl status"
