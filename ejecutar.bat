@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Primero ejecute instalar.bat
  pause
  exit /b 1
)
.venv\Scripts\python.exe -m pasajes_accesibles_cnrt.app
if errorlevel 1 pause
