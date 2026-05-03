@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1

set "INSTALL_DIR=%USERPROFILE%\voice-input"
set "GITHUB_REPO=artur-arc/voice-input"

cls
echo.
echo  ================================================
echo       Voice Input  --  Windows Installer
echo  ================================================
echo.
echo   This will take a few minutes. Do not close this window.
echo.

:: ── Python 3.11+ (try py launcher, python3, python) ──────────────────────────
echo -- Python check
set "PYTHON="
for %%P in (py python3 python) do (
    if not defined PYTHON (
        %%P --version >nul 2>&1
        if not errorlevel 1 set "PYTHON=%%P"
    )
)
if not defined PYTHON (
    echo.
    echo   Python not found.
    echo   Please install Python 3.11+ from:
    echo     https://www.python.org/downloads/
    echo   Check "Add Python to PATH" during installation, then re-run this file.
    goto :error
)
for /f "tokens=2" %%v in ('!PYTHON! --version 2^>^&1') do set "PY_VER=%%v"
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
echo   OK  Python !PY_VER! (!PYTHON!)

:: ── Download latest release zip via PowerShell (no git required) ─────────────
echo.
echo -- Downloading Voice Input
if exist "%INSTALL_DIR%" (
    echo   Removing previous installation...
    rmdir /s /q "%INSTALL_DIR%"
)
mkdir "%INSTALL_DIR%"

powershell -NoProfile -Command ^
    "$ErrorActionPreference = 'Stop';" ^
    "try {" ^
    "  $api = 'https://api.github.com/repos/%GITHUB_REPO%/releases/latest';" ^
    "  $rel = Invoke-RestMethod -Uri $api -Headers @{'User-Agent'='voice-input-installer'};" ^
    "  $asset = $rel.assets | Where-Object { $_.name -like '*windows*.zip' } | Select-Object -First 1;" ^
    "  if (-not $asset) { throw 'No Windows zip asset found in release ' + $rel.tag_name };" ^
    "  Write-Host ('  Downloading ' + $asset.name + '...');" ^
    "  Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $env:TEMP\vi-update.zip -UseBasicParsing;" ^
    "  Write-Host '  Extracting...';" ^
    "  Expand-Archive -Path $env:TEMP\vi-update.zip -DestinationPath '%INSTALL_DIR%' -Force;" ^
    "  Remove-Item $env:TEMP\vi-update.zip -Force;" ^
    "  Write-Host '  OK  Downloaded';" ^
    "} catch { Write-Host ('  ERROR: ' + $_); exit 1 }"
if errorlevel 1 (
    echo.
    echo   Download failed. Check your internet connection and try again.
    goto :error
)

:: ── Run setup ─────────────────────────────────────────────────────────────────
cd /d "%INSTALL_DIR%"
!PYTHON! setup.py
if errorlevel 1 goto :error
goto :end

:error
echo.
echo   Installation failed. See error above.
pause
exit /b 1

:end
