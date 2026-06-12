@echo off
setlocal
powershell.exe -NoExit -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-dev.ps1"
endlocal
