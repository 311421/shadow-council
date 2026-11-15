param([string]$ListenAddress = '127.0.0.1:8000')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Create .venv and install requirements.txt first. See README.md.'
}
& $pythonPath manage.py migrate
if ($LASTEXITCODE -ne 0) { throw 'Database migration failed.' }
& $pythonPath manage.py runserver $ListenAddress
