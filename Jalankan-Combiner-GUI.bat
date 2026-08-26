@echo off
setlocal
set "APP_DIR=%~dp0"
set "PYTHON_GUI=%APP_DIR%.venv\Scripts\python.exe"

if not exist "%PYTHON_GUI%" (
    echo.
    echo GUI belum diinstal di komputer ini.
    echo Buka PowerShell di folder proyek, lalu jalankan:
    echo   py -3.13 -m venv .venv
    echo   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

"%PYTHON_GUI%" "%APP_DIR%combine_gui.py"
if errorlevel 1 (
    echo.
    echo GUI berhenti karena ada kesalahan. Pesan di atas dapat dikirim ke IT.
    pause
)
