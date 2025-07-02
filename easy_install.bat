@echo off
cls

echo.
echo =================================
echo      POS Printer Installer
echo =================================
echo.

:: Check for administrator privileges and request if necessary
net session >nul 2>nul
if %errorLevel% neq 0 (
    echo [!] Administrator privileges are required.
    echo     Click 'Yes' on the UAC prompt to continue the installation.
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

:: Set PowerShell script path
set "SCRIPT_PATH=%~dp0installer.ps1"

echo [*] Checking for installer script...
echo    - Path: %SCRIPT_PATH%
echo.

:: Check if the installer script exists
if not exist "%SCRIPT_PATH%" (
    echo [!] Error: Installer script not found.
    echo     Please make sure 'installer.ps1' is in the same folder.
    echo.
    pause
    exit /b
)

echo [*] Starting PowerShell installer...
echo.

:: Execute PowerShell
powershell -ExecutionPolicy Bypass -File "%SCRIPT_PATH%"

echo.
echo =================================
echo  Installation process finished.
echo =================================
echo.
pause 