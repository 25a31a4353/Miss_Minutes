@echo off
REM ==============================================================================
REM  MISS MINUTES & JARVIS AI DESKTOP ASSISTANT - 1-CLICK SETUP SCRIPT
REM  Phase 8: Production Consolidation & Integration
REM ==============================================================================

echo.
echo ==================================================================
echo   🕒 WELCOME TO MISS MINUTES & JARVIS AI ASSISTANT SETUP 🕒
echo ==================================================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in your PATH.
    echo Please install Python 3.10+ from https://www.python.org/
    pause
    exit /b 1
)

echo [OK] Python detected:
python --version

if not exist ".venv" (
    echo [*] Creating isolated virtual environment (.venv)...
    python -m venv .venv
) else (
    echo [OK] Existing virtual environment found.
)

echo [*] Activating environment...
call .venv\Scripts\activate.bat

echo [*] Upgrading pip...
python -m pip install --upgrade pip

echo [*] Installing production dependencies from requirements.txt...
pip install -r requirements.txt

echo.
echo [*] Running automated self-diagnostics...
python main.py --diagnostics

echo.
echo ==================================================================
echo   [+] MISS MINUTES & JARVIS SETUP COMPLETED SUCCESSFULLY!
echo ==================================================================
echo.
echo How to launch:
echo   1. Desktop 1-Click:  Double-click "launch_miss_minutes.bat"
echo   2. Command Line:     python main.py
echo   3. Diagnostics:      python main.py --diagnostics
echo   4. Jarvis Dev Mode:  python main.py --jarvis
echo.
pause
