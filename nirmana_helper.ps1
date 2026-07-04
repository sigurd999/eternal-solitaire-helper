# Nirmana play helper launcher (PowerShell companion to nirmana_helper.bat).

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

$pyExe = "C:\Program Files\Python\Python313\python.exe"

if (-not (Test-Path $pyExe)) {
    $pyExe = "python"
}

Set-Location $scriptDir

& $pyExe (Join-Path $scriptDir "nirmana_helper.py") @args

Read-Host "Press Enter to close"
