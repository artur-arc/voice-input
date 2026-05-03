@echo off
setlocal enabledelayedexpansion

set "INSTALL_DIR=%USERPROFILE%\voice-input"
set "GITHUB_REPO=artur-arc/voice-input"

cls
echo.
echo  Voice Input - Windows Installer
echo  ================================
echo.
echo  This will take a few minutes. Do not close this window.
echo.

:: ── Python 3.11+ (try py launcher, python3, python) ──────────────────────────
echo Checking Python...
set "PYTHON="

py --version >nul 2>&1
if not errorlevel 1 ( set "PYTHON=py" & goto :python_found )
python3 --version >nul 2>&1
if not errorlevel 1 ( set "PYTHON=python3" & goto :python_found )
python --version >nul 2>&1
if not errorlevel 1 ( set "PYTHON=python" & goto :python_found )

echo.
echo  Python not found.
echo  Install Python 3.11+ from: https://www.python.org/downloads/
echo  Check "Add Python to PATH" during installation, then re-run this file.
goto :error

:python_found
for /f "tokens=2" %%V in ('!PYTHON! --version 2^>^&1') do set "PY_VER=%%V"
for /f "tokens=1 delims=." %%M in ("!PY_VER!") do set "PY_MAJOR=%%M"
for /f "tokens=2 delims=." %%m in ("!PY_VER!") do set "PY_MINOR=%%m"
if !PY_MAJOR! lss 3 ( echo  Python 3.11+ required. Found: !PY_VER! & goto :error )
if !PY_MINOR! lss 11 ( echo  Python 3.11+ required. Found: !PY_VER! & goto :error )
echo  OK  Python !PY_VER!

:: ── Download latest release zip via PowerShell ───────────────────────────────
echo.
echo Downloading Voice Input...
if exist "%INSTALL_DIR%" rmdir /s /q "%INSTALL_DIR%"
mkdir "%INSTALL_DIR%"

:: Write PS1 script line by line (avoids ^ continuation quoting issues)
set "PS1=%TEMP%\vi-install.ps1"
set "VI_DEST=%INSTALL_DIR%"

>  "%PS1%" echo $ErrorActionPreference = 'Stop'
>> "%PS1%" echo $dest = $env:VI_DEST
>> "%PS1%" echo $rel = Invoke-RestMethod 'https://api.github.com/repos/%GITHUB_REPO%/releases/latest' -Headers @{'User-Agent'='voice-input-installer'}
>> "%PS1%" echo $asset = $rel.assets ^| Where-Object { $_.name -like '*windows*.zip' } ^| Select-Object -First 1
>> "%PS1%" echo if (-not $asset) { Write-Host 'ERROR: No zip asset in this release'; exit 1 }
>> "%PS1%" echo $n = $asset.name
>> "%PS1%" echo Write-Host "  Downloading $n..."
>> "%PS1%" echo Invoke-WebRequest $asset.browser_download_url -OutFile "$env:TEMP\vi.zip" -UseBasicParsing
>> "%PS1%" echo Write-Host '  Extracting...'
>> "%PS1%" echo Expand-Archive "$env:TEMP\vi.zip" -DestinationPath $dest -Force
>> "%PS1%" echo Remove-Item "$env:TEMP\vi.zip" -Force
>> "%PS1%" echo Write-Host '  OK'

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%"
set "PS_ERR=%ERRORLEVEL%"
del "%PS1%" 2>nul
if %PS_ERR% neq 0 (
    echo.
    echo  Download failed. Check your internet connection.
    goto :error
)

:: ── Run setup.py ──────────────────────────────────────────────────────────────
echo.
echo Setting up...
cd /d "%INSTALL_DIR%"
!PYTHON! setup.py
if errorlevel 1 goto :error
goto :end

:error
echo.
echo  Installation failed. See error above.
pause
exit /b 1

:end
