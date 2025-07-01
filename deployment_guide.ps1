param(
    [Parameter(Mandatory=$true)]
    [string]$Version,
    
    [Parameter(Mandatory=$true)]
    [string]$OutputPath
)

# 색상 출력 함수
function Write-ColorOutput($Message, $Color = "White") {
    Write-Host $Message -ForegroundColor $Color
}

# 오류 처리 함수
function Handle-Error($Message, $Exception = $null) {
    Write-ColorOutput "❌ 오류: $Message" "Red"
    if ($Exception) {
        Write-ColorOutput "세부 정보: $($Exception.Message)" "Red"
    }
    exit 1
}

# 시작 메시지
Write-ColorOutput "🚀 POS 프린터 v$Version 빌드 시작" "Green"
Write-ColorOutput "출력 경로: $OutputPath" "Cyan"

# 필수 도구 확인
Write-ColorOutput "🔍 필수 도구 확인 중..." "Yellow"

# Python 확인
try {
    $pythonVersion = python --version 2>&1
    Write-ColorOutput "✅ Python: $pythonVersion" "Green"
} catch {
    Handle-Error "Python이 설치되지 않았거나 PATH에 없습니다." $_
}

# PyInstaller 확인
try {
    $pyinstallerVersion = pyinstaller --version 2>&1
    Write-ColorOutput "✅ PyInstaller: $pyinstallerVersion" "Green"
} catch {
    Write-ColorOutput "⚠️ PyInstaller가 설치되지 않았습니다. 설치 중..." "Yellow"
    pip install pyinstaller
    if ($LASTEXITCODE -ne 0) {
        Handle-Error "PyInstaller 설치에 실패했습니다."
    }
}

# 출력 디렉토리 생성
Write-ColorOutput "📁 출력 디렉토리 준비 중..." "Yellow"
if (Test-Path $OutputPath) {
    Remove-Item $OutputPath -Recurse -Force
}
New-Item -ItemType Directory -Path $OutputPath -Force | Out-Null

# 임시 빌드 디렉토리 정리
if (Test-Path "build") {
    Remove-Item "build" -Recurse -Force
}
if (Test-Path "dist") {
    Remove-Item "dist" -Recurse -Force
}

# PyInstaller로 실행파일 빌드
Write-ColorOutput "🏗️ 실행파일 빌드 중..." "Yellow"
try {
    # POSPrinter.spec 파일이 있으면 사용, 없으면 기본 설정으로 빌드
    if (Test-Path "POSPrinter.spec") {
        Write-ColorOutput "📋 POSPrinter.spec 파일을 사용하여 빌드합니다." "Cyan"
        pyinstaller POSPrinter.spec --clean --noconfirm
    } else {
        Write-ColorOutput "📋 기본 설정으로 빌드합니다." "Cyan"
        pyinstaller main.py --name POSPrinter --onefile --windowed --noconfirm `
            --add-data "src;src" `
            --add-data "printer_config.json;." `
            --hidden-import "PySide6.QtCore" `
            --hidden-import "PySide6.QtWidgets" `
            --hidden-import "PySide6.QtGui" `
            --hidden-import "websockets" `
            --hidden-import "requests" `
            --hidden-import "escpos"
    }
    
    if ($LASTEXITCODE -ne 0) {
        Handle-Error "PyInstaller 빌드에 실패했습니다."
    }
    Write-ColorOutput "✅ 빌드 완료!" "Green"
} catch {
    Handle-Error "빌드 과정에서 오류가 발생했습니다." $_
}

# 빌드 결과물 복사
Write-ColorOutput "📦 배포 파일 구성 중..." "Yellow"

# 실행파일 복사
$exePath = "dist\POSPrinter.exe"
if (Test-Path $exePath) {
    Copy-Item $exePath $OutputPath
    Write-ColorOutput "✅ 실행파일 복사 완료" "Green"
} else {
    Handle-Error "빌드된 실행파일을 찾을 수 없습니다: $exePath"
}

# 필수 설정 파일들 복사
$configFiles = @(
    "printer_config.json",
    "requirements.txt"
)

foreach ($file in $configFiles) {
    if (Test-Path $file) {
        Copy-Item $file $OutputPath
        Write-ColorOutput "✅ $file 복사 완료" "Green"
    } else {
        Write-ColorOutput "⚠️ $file 파일을 찾을 수 없습니다." "Yellow"
    }
}

# libusb DLL 복사 (USB 프린터 지원용)
if (Test-Path "libusb-1.0.dll") {
    Copy-Item "libusb-1.0.dll" $OutputPath
    Write-ColorOutput "✅ libusb-1.0.dll 복사 완료" "Green"
}

# 문서 파일들 복사
$docFiles = @(
    "README.md",
    "INSTALLATION_GUIDE.md"
)

foreach ($file in $docFiles) {
    if (Test-Path $file) {
        Copy-Item $file $OutputPath
        Write-ColorOutput "✅ $file 복사 완료" "Green"
    }
}

# 설치 스크립트 생성
Write-ColorOutput "📝 설치 스크립트 생성 중..." "Yellow"
$installerScript = @"
# POS 프린터 설치 스크립트 v$Version
param([switch]`$Silent)

if (-not `$Silent) {
    Write-Host "🖨️ POS 프린터 v$Version 설치를 시작합니다." -ForegroundColor Green
    Write-Host ""
}

# 관리자 권한 확인
if (-NOT ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Host "❌ 이 스크립트는 관리자 권한이 필요합니다." -ForegroundColor Red
    Write-Host "PowerShell을 관리자 권한으로 실행한 후 다시 시도해주세요." -ForegroundColor Yellow
    pause
    exit 1
}

# 설치 경로 설정
`$InstallPath = "`$env:ProgramFiles\POS Printer"
`$DesktopPath = [Environment]::GetFolderPath("Desktop")
`$StartMenuPath = "`$env:ProgramData\Microsoft\Windows\Start Menu\Programs"

try {
    # 설치 디렉토리 생성
    if (-not (Test-Path `$InstallPath)) {
        New-Item -ItemType Directory -Path `$InstallPath -Force | Out-Null
    }
    
    # 파일 복사
    Copy-Item "POSPrinter.exe" `$InstallPath -Force
    Copy-Item "printer_config.json" `$InstallPath -Force -ErrorAction SilentlyContinue
    Copy-Item "libusb-1.0.dll" `$InstallPath -Force -ErrorAction SilentlyContinue
    
    # 바탕화면 바로가기 생성
    `$WshShell = New-Object -comObject WScript.Shell
    `$Shortcut = `$WshShell.CreateShortcut("`$DesktopPath\POS 프린터.lnk")
    `$Shortcut.TargetPath = "`$InstallPath\POSPrinter.exe"
    `$Shortcut.WorkingDirectory = `$InstallPath
    `$Shortcut.Description = "POS 프린터 v$Version"
    `$Shortcut.Save()
    
    # 시작 메뉴 바로가기 생성
    `$StartMenuShortcut = `$WshShell.CreateShortcut("`$StartMenuPath\POS 프린터.lnk")
    `$StartMenuShortcut.TargetPath = "`$InstallPath\POSPrinter.exe"
    `$StartMenuShortcut.WorkingDirectory = `$InstallPath
    `$StartMenuShortcut.Description = "POS 프린터 v$Version"
    `$StartMenuShortcut.Save()
    
    if (-not `$Silent) {
        Write-Host "✅ 설치가 완료되었습니다!" -ForegroundColor Green
        Write-Host "📍 설치 위치: `$InstallPath" -ForegroundColor Cyan
        Write-Host "🖥️ 바탕화면에 바로가기가 생성되었습니다." -ForegroundColor Cyan
        Write-Host ""
        Write-Host "프로그램을 실행하려면 바탕화면의 'POS 프린터' 아이콘을 더블클릭하세요." -ForegroundColor Yellow
        pause
    }
    
} catch {
    Write-Host "❌ 설치 중 오류가 발생했습니다: `$(`$_.Exception.Message)" -ForegroundColor Red
    if (-not `$Silent) { pause }
    exit 1
}
"@

$installerScript | Out-File -FilePath "$OutputPath\installer.ps1" -Encoding UTF8
Write-ColorOutput "✅ installer.ps1 생성 완료" "Green"

# 제거 스크립트 생성
$uninstallerScript = @"
# POS 프린터 제거 스크립트
Write-Host "🗑️ POS 프린터를 제거합니다..." -ForegroundColor Yellow

`$InstallPath = "`$env:ProgramFiles\POS Printer"
`$DesktopShortcut = [Environment]::GetFolderPath("Desktop") + "\POS 프린터.lnk"
`$StartMenuShortcut = "`$env:ProgramData\Microsoft\Windows\Start Menu\Programs\POS 프린터.lnk"

try {
    # 프로세스 종료
    Get-Process -Name "POSPrinter" -ErrorAction SilentlyContinue | Stop-Process -Force
    
    # 파일 및 폴더 삭제
    if (Test-Path `$InstallPath) {
        Remove-Item `$InstallPath -Recurse -Force
    }
    
    # 바로가기 삭제
    if (Test-Path `$DesktopShortcut) {
        Remove-Item `$DesktopShortcut -Force
    }
    
    if (Test-Path `$StartMenuShortcut) {
        Remove-Item `$StartMenuShortcut -Force
    }
    
    Write-Host "✅ 제거가 완료되었습니다." -ForegroundColor Green
    
} catch {
    Write-Host "❌ 제거 중 오류: `$(`$_.Exception.Message)" -ForegroundColor Red
}

pause
"@

$uninstallerScript | Out-File -FilePath "$OutputPath\uninstaller.ps1" -Encoding UTF8
Write-ColorOutput "✅ uninstaller.ps1 생성 완료" "Green"

# 버전 정보 파일 생성
$versionInfo = @{
    version = $Version
    build_date = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    description = "POS 프린터 소프트웨어"
    build_type = "Release"
} | ConvertTo-Json -Depth 10

$versionInfo | Out-File -FilePath "$OutputPath\version.json" -Encoding UTF8
Write-ColorOutput "✅ version.json 생성 완료" "Green"

# 빌드 정보 요약
Write-ColorOutput "`n📊 빌드 완료 요약" "Green"
Write-ColorOutput "=====================" "Green"
Write-ColorOutput "버전: $Version" "Cyan"
Write-ColorOutput "출력 경로: $OutputPath" "Cyan"
Write-ColorOutput "빌드 시간: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" "Cyan"

# 파일 목록 출력
Write-ColorOutput "`n📁 생성된 파일들:" "Yellow"
Get-ChildItem $OutputPath | ForEach-Object {
    $size = if ($_.PSIsContainer) { "<DIR>" } else { "{0:N0} bytes" -f $_.Length }
    Write-ColorOutput "  $($_.Name) - $size" "White"
}

# 임시 파일 정리
Write-ColorOutput "`n🧹 임시 파일 정리 중..." "Yellow"
if (Test-Path "build") { Remove-Item "build" -Recurse -Force }
if (Test-Path "dist") { Remove-Item "dist" -Recurse -Force }

Write-ColorOutput "`n✅ 빌드가 성공적으로 완료되었습니다!" "Green"
Write-ColorOutput "📦 배포 파일은 $OutputPath 에 준비되어 있습니다." "Cyan" 