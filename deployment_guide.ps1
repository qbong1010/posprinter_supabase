param(
    [Parameter(Mandatory=$true)]
    [string]$Version,
    
    [Parameter(Mandatory=$true)]
    [string]$OutputPath
)

# Set UTF-8 encoding to prevent Korean character issues
$PSDefaultParameterValues['Out-File:Encoding'] = 'utf8'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Color output function
function Write-ColorOutput($Message, $Color = "White") {
    Write-Host $Message -ForegroundColor $Color
}

# Error handling function
function Handle-Error($Message, $Exception = $null) {
    Write-ColorOutput "ERROR: $Message" "Red"
    if ($Exception) {
        Write-ColorOutput "Details: $($Exception.Message)" "Red"
    }
    exit 1
}

# Start message
Write-ColorOutput "Building POS Printer v$Version" "Green"
Write-ColorOutput "Output path: $OutputPath" "Cyan"

# Check required tools
Write-ColorOutput "Checking required tools..." "Yellow"

# Check Python
try {
    $pythonVersion = python --version 2>&1
    Write-ColorOutput "Python: $pythonVersion" "Green"
} catch {
    Handle-Error "Python is not installed or not in PATH." $_
}

# Check PyInstaller
try {
    $pyinstallerVersion = pyinstaller --version 2>&1
    Write-ColorOutput "PyInstaller: $pyinstallerVersion" "Green"
} catch {
    Write-ColorOutput "PyInstaller not found. Installing..." "Yellow"
    pip install pyinstaller
    if ($LASTEXITCODE -ne 0) {
        Handle-Error "Failed to install PyInstaller."
    }
}

# Prepare output directory
Write-ColorOutput "Preparing output directory..." "Yellow"
if (Test-Path $OutputPath) {
    Remove-Item $OutputPath -Recurse -Force
}
New-Item -ItemType Directory -Path $OutputPath -Force | Out-Null

# Clean previous build files
if (Test-Path "build") {
    Remove-Item "build" -Recurse -Force
}
if (Test-Path "dist") {
    Remove-Item "dist" -Recurse -Force
}

# Build executable with PyInstaller
Write-ColorOutput "Building executable..." "Yellow"
try {
    if (Test-Path "POSPrinter.spec") {
        Write-ColorOutput "Using POSPrinter.spec file (onedir mode configured in spec)" "Cyan"
        pyinstaller POSPrinter.spec --clean --noconfirm
    } else {
        Write-ColorOutput "Using default build settings (onedir mode)" "Cyan"
        pyinstaller main.py --name POSPrinter --onedir --windowed --noconfirm `
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
        Handle-Error "PyInstaller build failed."
    }
    Write-ColorOutput "Build completed!" "Green"
} catch {
    Handle-Error "Error occurred during build process." $_
}

# Copy build results
Write-ColorOutput "Organizing distribution files..." "Yellow"

# Copy executable folder
$distPath = "dist\POSPrinter"
if (Test-Path $distPath) {
    Copy-Item $distPath $OutputPath -Recurse -Force
    Write-ColorOutput "Executable folder copied" "Green"
} else {
    Handle-Error "Built executable folder not found: $distPath"
}

# Copy additional files
$configFiles = @(
    "printer_config.json",
    "requirements.txt"
)

foreach ($file in $configFiles) {
    if (Test-Path $file) {
        Copy-Item $file "$OutputPath\POSPrinter" -Force
        Write-ColorOutput "$file copied" "Green"
    } else {
        Write-ColorOutput "Warning: $file not found" "Yellow"
    }
}

# Copy libusb DLL if exists
if (Test-Path "libusb-1.0.dll") {
    Copy-Item "libusb-1.0.dll" "$OutputPath\POSPrinter" -Force
    Write-ColorOutput "libusb-1.0.dll copied" "Green"
}

# Copy documentation files
$docFiles = @(
    "README.md",
    "INSTALLATION_GUIDE.md"
)

foreach ($file in $docFiles) {
    if (Test-Path $file) {
        Copy-Item $file $OutputPath -Force
        Write-ColorOutput "$file copied" "Green"
    }
}

# Copy installation batch file
if (Test-Path "AutoInstall.bat") {
    Copy-Item "AutoInstall.bat" $OutputPath -Force
    Write-ColorOutput "AutoInstall.bat copied" "Green"
}

# Create installer script
Write-ColorOutput "Creating installer script..." "Yellow"
$installerScript = @"
# POS Printer Installer Script v$Version
param([switch]`$Silent)

if (-not `$Silent) {
    Write-Host "Installing POS Printer v$Version..." -ForegroundColor Green
    Write-Host ""
}

# Check administrator privileges
if (-NOT ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Host "ERROR: Administrator privileges required." -ForegroundColor Red
    Write-Host "Please run PowerShell as administrator and try again." -ForegroundColor Yellow
    pause
    exit 1
}

# Set installation paths
`$InstallPath = "`$env:ProgramFiles\POS Printer"
`$DesktopPath = [Environment]::GetFolderPath("Desktop")
`$StartMenuPath = "`$env:ProgramData\Microsoft\Windows\Start Menu\Programs"

try {
    # Create installation directory
    if (-not (Test-Path `$InstallPath)) {
        New-Item -ItemType Directory -Path `$InstallPath -Force | Out-Null
    }
    
    # Copy files
    Copy-Item "POSPrinter\*" `$InstallPath -Recurse -Force
    
    # Create desktop shortcut
    `$WshShell = New-Object -comObject WScript.Shell
    `$Shortcut = `$WshShell.CreateShortcut("`$DesktopPath\POS Printer.lnk")
    `$Shortcut.TargetPath = "`$InstallPath\POSPrinter.exe"
    `$Shortcut.WorkingDirectory = `$InstallPath
    `$Shortcut.Description = "POS Printer v$Version"
    `$Shortcut.Save()
    
    # Create start menu shortcut
    `$StartMenuShortcut = `$WshShell.CreateShortcut("`$StartMenuPath\POS Printer.lnk")
    `$StartMenuShortcut.TargetPath = "`$InstallPath\POSPrinter.exe"
    `$StartMenuShortcut.WorkingDirectory = `$InstallPath
    `$StartMenuShortcut.Description = "POS Printer v$Version"
    `$StartMenuShortcut.Save()
    
    if (-not `$Silent) {
        Write-Host "Installation completed successfully!" -ForegroundColor Green
        Write-Host "Installation location: `$InstallPath" -ForegroundColor Cyan
        Write-Host "Desktop shortcut created." -ForegroundColor Cyan
        Write-Host ""
        Write-Host "Double-click the 'POS Printer' icon on desktop to run the program." -ForegroundColor Yellow
        pause
    }
    
} catch {
    Write-Host "ERROR during installation: `$(`$_.Exception.Message)" -ForegroundColor Red
    if (-not `$Silent) { pause }
    exit 1
}
"@

$installerScript | Out-File -FilePath "$OutputPath\installer.ps1" -Encoding UTF8
Write-ColorOutput "installer.ps1 created" "Green"

# Create uninstaller script
$uninstallerScript = @"
# POS Printer Uninstaller Script
Write-Host "Uninstalling POS Printer..." -ForegroundColor Yellow

`$InstallPath = "`$env:ProgramFiles\POS Printer"
`$DesktopShortcut = [Environment]::GetFolderPath("Desktop") + "\POS Printer.lnk"
`$StartMenuShortcut = "`$env:ProgramData\Microsoft\Windows\Start Menu\Programs\POS Printer.lnk"

try {
    # Stop process
    Get-Process -Name "POSPrinter" -ErrorAction SilentlyContinue | Stop-Process -Force
    
    # Remove files and folders
    if (Test-Path `$InstallPath) {
        Remove-Item `$InstallPath -Recurse -Force
    }
    
    # Remove shortcuts
    if (Test-Path `$DesktopShortcut) {
        Remove-Item `$DesktopShortcut -Force
    }
    
    if (Test-Path `$StartMenuShortcut) {
        Remove-Item `$StartMenuShortcut -Force
    }
    
    Write-Host "Uninstallation completed." -ForegroundColor Green
    
} catch {
    Write-Host "ERROR during uninstallation: `$(`$_.Exception.Message)" -ForegroundColor Red
}

pause
"@

$uninstallerScript | Out-File -FilePath "$OutputPath\uninstaller.ps1" -Encoding UTF8
Write-ColorOutput "uninstaller.ps1 created" "Green"

# Create version info file
$versionInfo = New-Object -TypeName PSObject
$versionInfo | Add-Member -MemberType NoteProperty -Name "version" -Value $Version
$versionInfo | Add-Member -MemberType NoteProperty -Name "build_date" -Value (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
$versionInfo | Add-Member -MemberType NoteProperty -Name "description" -Value "POS Printer Software"
$versionInfo | Add-Member -MemberType NoteProperty -Name "build_type" -Value "Release"

$versionInfo | ConvertTo-Json -Depth 10 | Out-File -FilePath "$OutputPath\POSPrinter\version.json" -Encoding UTF8
Write-ColorOutput "version.json created" "Green"

# Build summary
Write-ColorOutput "`nBuild Summary" "Green"
Write-ColorOutput "=====================" "Green"
Write-ColorOutput "Version: $Version" "Cyan"
Write-ColorOutput "Output Path: $OutputPath" "Cyan"
Write-ColorOutput "Build Time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" "Cyan"

# File list
Write-ColorOutput "`nGenerated Files:" "Yellow"
Get-ChildItem $OutputPath | ForEach-Object {
    $size = if ($_.PSIsContainer) { "<DIR>" } else { "{0:N0} bytes" -f $_.Length }
    Write-ColorOutput "  $($_.Name) - $size" "White"
}

# Cleanup
Write-ColorOutput "`nCleaning up temporary files..." "Yellow"
if (Test-Path "build") { Remove-Item "build" -Recurse -Force }
if (Test-Path "dist") { Remove-Item "dist" -Recurse -Force }

Write-ColorOutput "`nBuild completed successfully!" "Green"
Write-ColorOutput "Distribution files are ready in: $OutputPath" "Cyan" 