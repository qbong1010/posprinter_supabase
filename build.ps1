# ========================================
# POS Printer Build Script
# ========================================

# 한글 깨짐 방지를 위해 터미널과 파워쉘의 출력 인코딩을 UTF-8로 강제 설정
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# Set execution policy
try {
    $currentPolicy = Get-ExecutionPolicy -Scope CurrentUser
    if ($currentPolicy -eq "Restricted") {
        Write-Host "Setting PowerShell execution policy..." -ForegroundColor Yellow
        Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
    }
} catch {
    # Continue if execution policy setting fails
}

Write-Host "POS Printer Build Starting..." -ForegroundColor Green
Write-Host ""

# Check script location
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$scriptName = Split-Path -Leaf $MyInvocation.MyCommand.Definition

Write-Host "Script location: $scriptDir" -ForegroundColor Gray
Write-Host "Script name: $scriptName" -ForegroundColor Gray
Write-Host ""

# Check administrator privileges
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")

if (-NOT $isAdmin) {
    Write-Host "Administrator privileges required." -ForegroundColor Yellow
    Write-Host "Attempting to restart with administrator privileges..." -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Please click 'Yes' when UAC dialog appears." -ForegroundColor Green
    Write-Host ""
    
    try {
        $scriptPath = Join-Path $scriptDir $scriptName
        Write-Host "Restarting script: $scriptPath" -ForegroundColor Gray
        
        Start-Sleep -Seconds 3
        
        $process = Start-Process PowerShell -Verb RunAs -ArgumentList "-NoExit", "-ExecutionPolicy Bypass", "-Command", "& '$scriptPath'" -PassThru
        
        if ($process) {
            Write-Host "Administrator window launched." -ForegroundColor Green
            exit
        } else {
            throw "Failed to start process"
        }
        
    } catch {
        Write-Host ""
        Write-Host "Auto restart failed: $($_.Exception.Message)" -ForegroundColor Red
        Write-Host ""
        Write-Host "Manual execution steps:" -ForegroundColor Yellow
        Write-Host "1. Search 'PowerShell' in Start menu" -ForegroundColor White
        Write-Host "2. Right-click -> 'Run as administrator'" -ForegroundColor White
        Write-Host "3. Execute these commands:" -ForegroundColor White
        Write-Host ""
        Write-Host "   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser" -ForegroundColor Gray
        Write-Host "   cd '$scriptDir'" -ForegroundColor Gray
        Write-Host "   .\$scriptName" -ForegroundColor Gray
        Write-Host ""
        Write-Host "Press any key to continue..." -ForegroundColor Cyan
        $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
        exit 1
    }
}

# Check Python installation
Write-Host "Checking Python installation..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Python is installed: $pythonVersion" -ForegroundColor Green
    } else {
        throw "Python not found"
    }
} catch {
    Write-Host "Python is not installed." -ForegroundColor Red
    Write-Host ""
    Write-Host "Do you want to install Python automatically? (Y/N): " -ForegroundColor Yellow -NoNewline
    $response = Read-Host
    
    if ($response -eq 'Y' -or $response -eq 'y') {
        Write-Host "Installing Python..." -ForegroundColor Yellow
        
        $pythonUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
        $pythonInstaller = "$env:TEMP\python-installer.exe"
        
        try {
            Invoke-WebRequest -Uri $pythonUrl -OutFile $pythonInstaller
            Start-Process -FilePath $pythonInstaller -ArgumentList "/quiet", "InstallAllUsers=0", "PrependPath=1", "Include_test=0" -Wait
            Remove-Item $pythonInstaller -Force
            
            # Refresh PATH
            $machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
            $userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
            $env:Path = $machinePath + ";" + $userPath
            
            Write-Host "Python installation completed!" -ForegroundColor Green
        } catch {
            Write-Host "Python auto-installation failed." -ForegroundColor Red
            Write-Host "Please install Python manually from https://www.python.org" -ForegroundColor Yellow
            pause
            exit 1
        }
    } else {
        Write-Host "Cannot proceed without Python installation." -ForegroundColor Red
        pause
        exit 1
    }
}

# Setup virtual environment
Write-Host "Setting up virtual environment..." -ForegroundColor Yellow
if (-not (Test-Path "venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Cyan
    python -m venv venv
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Cyan
if (Test-Path "venv\Scripts\Activate.ps1") {
    & .\venv\Scripts\Activate.ps1
} else {
    Write-Host "Failed to activate virtual environment." -ForegroundColor Red
    pause
    exit 1
}

# Install dependencies
Write-Host "Installing required packages..." -ForegroundColor Yellow
Write-Host "This may take several minutes..." -ForegroundColor Cyan
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if ($LASTEXITCODE -ne 0) {
    Write-Host "Package installation failed." -ForegroundColor Red
    pause
    exit 1
}

# Clean build directories
Write-Host "Cleaning previous build files..." -ForegroundColor Yellow
if (Test-Path "build") { Remove-Item "build" -Recurse -Force }
if (Test-Path "dist") { Remove-Item "dist" -Recurse -Force }

# Build executable with PyInstaller
Write-Host "Building executable..." -ForegroundColor Yellow
Write-Host "This process may take several minutes..." -ForegroundColor Cyan

pyinstaller POSPrinter.spec --clean --noconfirm

if ($LASTEXITCODE -ne 0) {
    Write-Host "Executable build failed." -ForegroundColor Red
    pause
    exit 1
}

# Check build result
if (Test-Path "dist\POSPrinter.exe") {
    Write-Host "Executable created successfully!" -ForegroundColor Green
} else {
    Write-Host "Executable not found." -ForegroundColor Red
    pause
    exit 1
}

# --- 설치 시작 ---
Write-Host ""
Write-Host "----------------------------------------" -ForegroundColor DarkCyan
Write-Host "설치를 시작합니다..." -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor DarkCyan
Write-Host ""

try {
    # 1. 설치 경로 정의 (사용자 요청에 따라 C:\Pos Printer 로 변경)
    $InstallPath = "C:\Pos Printer"
    $DesktopPath = [Environment]::GetFolderPath("Desktop")

    Write-Host "설치 폴더 생성: $InstallPath" -ForegroundColor Cyan
    if (-not (Test-Path $InstallPath)) {
        New-Item -ItemType Directory -Path $InstallPath -Force | Out-Null
    }
    
    # 2. 파일 복사
    Write-Host "애플리케이션 파일을 복사합니다..." -ForegroundColor Cyan
    Copy-Item "dist\POSPrinter.exe" $InstallPath -Force
    if (Test-Path "printer_config.json") {
        Copy-Item "printer_config.json" $InstallPath -Force
    }
    if (Test-Path "version.json") {
        Copy-Item "version.json" $InstallPath -Force
    }
    if (Test-Path "default.env") {
        Copy-Item "default.env" (Join-Path $InstallPath ".env") -Force
    }
    
    # 3. 바탕화면 바로가기 생성
    Write-Host "바탕화면에 바로가기를 생성합니다..." -ForegroundColor Cyan
    $WshShell = New-Object -comObject WScript.Shell
    $ShortcutPath = Join-Path $DesktopPath "POS Printer.lnk"
    $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = (Join-Path $InstallPath "POSPrinter.exe")
    $Shortcut.WorkingDirectory = $InstallPath
    $Shortcut.Save()
    
    # 4. 디버그용 실행 파일 생성
    Write-Host "디버그용 실행 파일을 생성합니다..." -ForegroundColor Cyan
    $debugScript = @"
@echo off
echo Running POSPrinter in debug mode...
echo Any errors will be logged to debug_output.log

".\POSPrinter.exe" > "debug_output.log" 2>&1

echo.
echo Execution finished.
echo If the program did not run, please check the debug_output.log file and send it to the developer.
pause
"@
    $debugScriptPath = Join-Path $InstallPath "debug_run.bat"
    $debugScript | Out-File -FilePath $debugScriptPath -Encoding OEM

    Write-Host ""
    Write-Host "✅ 설치가 성공적으로 완료되었습니다!" -ForegroundColor Green
    Write-Host "바탕화면의 'POS Printer' 아이콘을 더블클릭하여 실행하세요." -ForegroundColor Yellow
    
} catch {
    Write-Host ""
    Write-Host "❌ 설치 실패: $($_.Exception.Message)" -ForegroundColor Red
    pause
    exit 1
}

# 임시 빌드 파일 정리
Write-Host ""
Write-Host "임시 파일을 정리합니다..." -ForegroundColor Gray
if (Test-Path "build") { Remove-Item "build" -Recurse -Force }
if (Test-Path "dist") { Remove-Item "dist" -Recurse -Force }

Write-Host ""
Write-Host "🎉 모든 작업이 완료되었습니다!" -ForegroundColor Green
pause 