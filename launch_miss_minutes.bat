@echo off
REM ==============================================================================
REM  MISS MINUTES & JARVIS AI DESKTOP ASSISTANT - 1-CLICK LAUNCHER
REM  Phase 8: Desktop Launch Readiness
REM
REM  How to use:
REM  - Double-click directly from Windows Explorer, or
REM  - Right-click -> "Send to" -> "Desktop (create shortcut)", or
REM  - Run from command line: launch_miss_minutes.bat [--console]
REM ==============================================================================

setlocal enabledelayedexpansion
cd /d "%~dp0"

REM Determine Python executable (.venv preferred over system)
set "PYTHON_EXE="
set "PYTHONW_EXE="

if exist "%~dp0.venv\Scripts\pythonw.exe" (
    set "PYTHONW_EXE=%~dp0.venv\Scripts\pythonw.exe"
)
if exist "%~dp0.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
)

if not defined PYTHONW_EXE (
    where pythonw >nul 2>&1
    if !errorlevel! equ 0 (
        for /f "tokens=*" %%i in ('where pythonw') do (
            if not defined PYTHONW_EXE set "PYTHONW_EXE=%%i"
        )
    )
)

if not defined PYTHON_EXE (
    where python >nul 2>&1
    if !errorlevel! equ 0 (
        for /f "tokens=*" %%i in ('where python') do (
            if not defined PYTHON_EXE set "PYTHON_EXE=%%i"
        )
    )
)

REM Check if Python was found
if not defined PYTHON_EXE if not defined PYTHONW_EXE (
    echo [ERROR] Python was not found on your system.
    echo Please install Python 3.10+ or run install.bat first.
    pause
    exit /b 1
)

REM If user requested console or diagnostics, use python.exe with output
if "%1"=="--console" (
    shift
    "%PYTHON_EXE%" "%~dp0main.py" %*
    goto :eof
)
if "%1"=="--diagnostics" (
    "%PYTHON_EXE%" "%~dp0main.py" --diagnostics
    pause
    goto :eof
)
if "%1"=="--jarvis" (
    shift
    "%PYTHON_EXE%" "%~dp0main.py" --jarvis %*
    goto :eof
)

REM Default: Launch windowed mode with pythonw.exe (no persistent command prompt)
if defined PYTHONW_EXE (
    start "" "%PYTHONW_EXE%" "%~dp0main.py" %*
) else (
    start "" "%PYTHON_EXE%" "%~dp0main.py" %*
)

exit /b 0
