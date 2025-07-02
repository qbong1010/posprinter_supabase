# Clean Build Script for POS Printer
# USB 훅 문제를 자동으로 해결하는 빌드 스크립트

param(
    [Parameter(Mandatory=$true)]
    [string]$Version,
    
    [Parameter(Mandatory=$true)]
    [string]$OutputPath
)

Write-Host "Clean Build Process Started..." -ForegroundColor Green

# 1. USB 훅 임시 비활성화
$hookPath = python -c "import _pyinstaller_hooks_contrib.hooks.stdhooks; import os; print(os.path.dirname(_pyinstaller_hooks_contrib.hooks.stdhooks.__file__) + '\hook-usb.py')"
$hookBackup = $hookPath + ".bak"

if (Test-Path $hookPath) {
    Write-Host "USB hook 임시 비활성화..." -ForegroundColor Yellow
    Move-Item $hookPath $hookBackup -Force
}

try {
    # 2. 정상 빌드 진행
    .\deployment_guide.ps1 -Version $Version -OutputPath $OutputPath
    
    Write-Host "빌드 완료!" -ForegroundColor Green
} finally {
    # 3. USB 훅 복원
    if (Test-Path $hookBackup) {
        Write-Host "USB hook 복원..." -ForegroundColor Yellow
        Move-Item $hookBackup $hookPath -Force
    }
}

Write-Host "Clean Build Process Completed!" -ForegroundColor Green 