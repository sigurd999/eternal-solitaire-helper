@echo off
rem Nirmana play helper launcher. Double-click to run.
chcp 65001 >nul
setlocal
cd /d "%~dp0"

set "PYEXE=C:\Program Files\Python\Python313\python.exe"
if not exist "%PYEXE%" set "PYEXE=python"

"%PYEXE%" "%~dp0nirmana_helper.py" %*

echo.
pause
endlocal
