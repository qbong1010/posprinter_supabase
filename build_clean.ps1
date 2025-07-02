# Clean Build Script for POS Printer
# USB hook issue auto-resolver build script

param(
    [Parameter(Mandatory=$true)]
    [string]$Version,
    
    [Parameter(Mandatory=$true)]
    [string]$OutputPath
)

Write-Host "Clean Build Process Started..." -ForegroundColor Green

# 1. Temporarily disable USB hook (if module exists)
$hookPath = $null
$hookBackup = $null

try {
    $hookPath = python -c "import _pyinstaller_hooks_contrib.hooks.stdhooks; import os; print(os.path.dirname(_pyinstaller_hooks_contrib.hooks.stdhooks.__file__) + '\hook-usb.py')" 2>$null
    if ($hookPath -and (Test-Path $hookPath)) {
        $hookBackup = $hookPath + ".bak"
        Write-Host "Temporarily disabling USB hook..." -ForegroundColor Yellow
        Move-Item $hookPath $hookBackup -Force
    }
} catch {
    Write-Host "Skipping USB hook processing (module not found)" -ForegroundColor Yellow
}

try {
    # 2. Proceed with normal build
    .\deployment_guide.ps1 -Version $Version -OutputPath $OutputPath
    
    Write-Host "Build completed!" -ForegroundColor Green
} finally {
    # 3. Restore USB hook (if backup exists)
    if ($hookBackup -and (Test-Path $hookBackup)) {
        Write-Host "Restoring USB hook..." -ForegroundColor Yellow
        Move-Item $hookBackup $hookPath -Force
    }
}

Write-Host "Clean Build Process Completed!" -ForegroundColor Green 