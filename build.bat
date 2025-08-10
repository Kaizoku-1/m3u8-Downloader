@echo off
echo ===================================
echo  M3U8 Downloader Pro Build Script
echo ===================================

echo.
echo [1/3] Checking for Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in your PATH.
    echo Please install Python 3 from python.org and try again.
    pause
    exit /b 1
)

echo.
echo [2/3] Installing dependencies from src/requirements.txt...
pip install -r src/requirements.txt
if %errorlevel% neq 0 (
    echo Error: Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo [3/3] Running PyInstaller to build the .exe...
pyinstaller --noconfirm --onefile --windowed --name M3U8_Downloader_Pro --icon="NONE" src/main_gui.py
if %errorlevel% neq 0 (
    echo Error: PyInstaller failed to build the executable.
    pause
    exit /b 1
)

echo.
echo ===================================
echo  Build successful!
echo ===================================
echo The executable can be found in the 'dist' folder:
echo dist/M3U8_Downloader_Pro.exe
echo.
pause
