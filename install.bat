@echo off
REM ==============================================================================
REM  JARVIS AI PERSONAL ASSISTANT - 1-CLICK WINDOWS SETUP SCRIPT
REM ==============================================================================

echo.
echo ==================================================================
echo           ⚡ WELCOME TO JARVIS AI ASSISTANT SETUP ⚡
echo ==================================================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [X] Python is not installed or not in PATH. Please install Python 3.10+ from python.org
    pause
    exit /b
)

echo [OK] Python detected.
if not exist ".venv" (
    echo [*] Creating virtual environment (.venv)...
    python -m venv .venv
)

echo [*] Activating environment...
call .venv\Scripts\activate.bat

echo [*] Installing dependencies...
pip install --upgrade pip
pip install -r requirements.txt
pip install pyttsx3 pyaudio

echo.
echo ==================================================================
echo           [+] JARVIS SETUP COMPLETED SUCCESSFULLY!
echo ==================================================================
echo.
echo To start Jarvis:
echo     call .venv\Scripts\activate.bat
echo     python jarvis_voice.py
echo.
pause
python jarvis_voice.py
