@echo off
cd /d "%~dp0"
title Build Hi Ultimate Lite V4
where py >nul 2>nul
if errorlevel 1 (echo Python is required.&pause&exit /b 1)
if not exist ".buildenv" py -m venv .buildenv
call ".buildenv\Scripts\activate.bat"
python -m pip install --upgrade pip
pip install -r requirements.txt
pyinstaller HiUltimateLiteV4.spec --clean --noconfirm
echo.
echo Build complete: dist\HiUltimateLiteV4.exe
pause
