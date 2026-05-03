@echo off
setlocal enabledelayedexpansion

set "INSTALL_DIR=%USERPROFILE%\voice-input"
set "GITHUB_REPO=artur-arc/voice-input"
set "PYTHON_VER=3.11.9"
set "PYTHON_URL=https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"

cls
echo.
echo  Voice Input - Windows Installer
echo  ================================
echo.
echo  This will take a few minutes. Do not close this window.
echo.

:: ── Python 3.11+ ──────────────────────────────────────────────────────────────
echo Checking Python...
call :find_python
if defined PYTHON goto :python_ok

echo  Python not found. Installing automatically...
echo.

:: Try winget first (available on Windows 10 1709+ and Windows 11)
winget --version >nul 2>&1
if not errorlevel 1 (
    echo  Trying winget...
    winget install --id Python.Python.3.11 -e --silent --scope user ^
        --accept-package-agreements --accept-source-agreements
    if not errorlevel 1 (
        call :refresh_path
        call :find_python
        if defined PYTHON goto :python_ok
    )
)

:: Fallback: download Python installer directly from python.org
echo  Downloading Python %PYTHON_VER% installer...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "Invoke-WebRequest '%PYTHON_URL%' -OutFile '$env:TEMP\python-installer.exe' -UseBasicParsing"
if errorlevel 1 (
    echo.
    echo  Download failed. Please install Python 3.11+ manually from:
    echo    https://www.python.org/downloads/
    echo  Check "Add Python to PATH" during installation, then re-run this file.
    goto :error
)
echo  Installing Python %PYTHON_VER%...
"%TEMP%\python-installer.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1
del "%TEMP%\python-installer.exe" 2>nul

call :refresh_path
call :find_python
if not defined PYTHON (
    echo  Python installation failed. Please install manually from:
    echo    https://www.python.org/downloads/
    goto :error
)

:python_ok
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

:: ── Helpers ───────────────────────────────────────────────────────────────────

:find_python
set "PYTHON="
py      --version >nul 2>&1 && set "PYTHON=py"      && goto :eof
python3 --version >nul 2>&1 && set "PYTHON=python3" && goto :eof
python  --version >nul 2>&1 && set "PYTHON=python"  && goto :eof
goto :eof

:refresh_path
powershell -NoProfile -Command ^
    "$p = [Environment]::GetEnvironmentVariable('PATH','Machine') + ';' + [Environment]::GetEnvironmentVariable('PATH','User'); $p | Out-File '$env:TEMP\vi-path.txt' -Encoding ASCII -NoNewline"
set /p "NEW_PATH=" < "%TEMP%\vi-path.txt"
del "%TEMP%\vi-path.txt" 2>nul
if defined NEW_PATH set "PATH=!NEW_PATH!"
goto :eof

:error
echo.
echo  Installation failed. See error above.
pause
exit /b 1

:end
