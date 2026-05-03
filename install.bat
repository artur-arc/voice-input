@echo off
setlocal enabledelayedexpansion

set "REPO=https://github.com/artur-arc/voice-input.git"
set "INSTALL_DIR=%USERPROFILE%\voice-input"

cls
echo.
echo  ╔════════════════════════════════════════╗
echo  ║     Voice Input — Windows Installer   ║
echo  ╚════════════════════════════════════════╝
echo.
echo   This will take a few minutes. Do not close this window.
echo.

:: ── Python 3.11+ ──────────────────────────────────────────────────────────────
echo ── Python check
python --version >nul 2>&1
if errorlevel 1 (
    echo   Python not found.
    echo   Please install Python 3.11+ from https://www.python.org/downloads/
    echo   Make sure to check "Add Python to PATH" during installation.
    goto :error
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set "PY_VER=%%v"
for /f "tokens=1 delims=." %%M in ("!PY_VER!") do set "PY_MAJOR=%%M"
for /f "tokens=2 delims=." %%m in ("!PY_VER!") do set "PY_MINOR=%%m"
if !PY_MAJOR! lss 3 (
    echo   Python 3.11+ required. Found: !PY_VER!
    goto :error
)
if !PY_MINOR! lss 11 (
    echo   Python 3.11+ required. Found: !PY_VER!
    goto :error
)
echo   ✓ Python !PY_VER!

:: ── Git ───────────────────────────────────────────────────────────────────────
echo ── Git check
git --version >nul 2>&1
if errorlevel 1 (
    echo   Git not found.
    echo   Please install Git from https://git-scm.com/download/win
    goto :error
)
echo   ✓ Git ready

:: ── Clone or update ───────────────────────────────────────────────────────────
echo.
echo ── Downloading Voice Input
if exist "%INSTALL_DIR%\.git" (
    echo   Updating to latest version...
    git -C "%INSTALL_DIR%" pull --ff-only
    if errorlevel 1 (
        echo   Update failed. Check your internet connection.
        goto :error
    )
    echo   ✓ Updated
) else (
    if exist "%INSTALL_DIR%" (
        echo   Removing existing directory...
        rmdir /s /q "%INSTALL_DIR%"
    )
    echo   Cloning repository...
    git clone "%REPO%" "%INSTALL_DIR%"
    if errorlevel 1 (
        echo   Clone failed. Check your internet connection.
        goto :error
    )
    echo   ✓ Downloaded to %INSTALL_DIR%
)

:: ── Run Python installer ──────────────────────────────────────────────────────
cd /d "%INSTALL_DIR%"
python setup-windows.py
if errorlevel 1 goto :error
goto :end

:error
echo.
echo   Installation failed. See error above.
pause
exit /b 1

:end
