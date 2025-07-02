# Usage: .\release.ps1 -Version "1.2.1" -Message "Added new features"

param(
    [Parameter(Mandatory=$true)]
    [string]$Version,
    
    [Parameter(Mandatory=$false)]
    [string]$Message = "Release v$Version"
)

# UTF-8 encoding settings
$PSDefaultParameterValues['Out-File:Encoding'] = 'utf8'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Write-Step($Message, $Color = "Cyan") {
    Write-Host "`n🚀 $Message" -ForegroundColor $Color
}

function Write-Success($Message) {
    Write-Host "✅ $Message" -ForegroundColor Green
}

function Write-Error($Message) {
    Write-Host "❌ $Message" -ForegroundColor Red
    exit 1
}

# Check GitHub CLI
try {
    gh --version | Out-Null
} catch {
    Write-Error "GitHub CLI is not installed. Cannot use 'gh' command."
}

Write-Step "Starting POS Printer v$Version release"

# 1. Check Git status
Write-Step "Checking Git status..."
$gitStatus = git status --porcelain
if ($gitStatus) {
    Write-Host "There are uncommitted changes. Do you want to commit them? (y/N): " -NoNewline -ForegroundColor Yellow
    $response = Read-Host
    if ($response -match '^[yY]') {
        git add .
        git commit -m $Message
        git push origin main
        Write-Success "Changes have been committed."
    } else {
        Write-Error "Please commit your changes before proceeding with the release."
    }
}

# 2. Update version information
Write-Step "Updating version.json..."
$versionInfo = @{
    version = $Version
    build_date = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    description = "POS Printer Software"
    build_type = "Release"
}
$versionInfo | ConvertTo-Json -Depth 10 | Out-File -FilePath "version.json" -Encoding UTF8
Write-Success "version.json updated successfully"

# 3. Execute build
Write-Step "Building application..."
try {
    .\build_clean.ps1 -Version $Version -OutputPath ".\release"
    Write-Success "Build completed"
} catch {
    Write-Error "Build failed: $_"
}

# 4. Create zip file
Write-Step "Compressing release files..."
$zipName = "POSPrinter_v$Version.zip"
if (Test-Path $zipName) {
    Remove-Item $zipName -Force
}
Compress-Archive -Path ".\release\*" -DestinationPath $zipName -Force
Write-Success "Compression completed: $zipName"

# 5. Create and push Git tag
Write-Step "Creating Git tag..."
$tagName = "v$Version"
try {
    git tag $tagName
    git push origin $tagName
    Write-Success "Tag created and pushed: $tagName"
} catch {
    Write-Error "Failed to create tag: $_"
}

# 6. Create GitHub release
Write-Step "Creating GitHub release..."
try {
    $releaseNotes = @"
## POS Printer v$Version

### Changes
$Message

### Installation
1. Download the attached ZIP file
2. Extract the contents  
3. Run ``간편설치.bat`` as administrator

### Update Instructions
- Existing users: Click 'Check for Updates' button in the application
- Downloads and installs automatically

### System Requirements
- Windows 10 or higher
- Administrator privileges (installation only)

Build Date: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
"@

    gh release create $tagName $zipName `
        --title "POS Printer v$Version" `
        --notes $releaseNotes
        
    Write-Success "GitHub release created successfully"
} catch {
    Write-Error "Failed to create GitHub release: $_"
}

# 7. Cleanup
Write-Step "Cleaning up..."
if (Test-Path $zipName) {
    Remove-Item $zipName -Force
    Write-Success "Temporary zip file deleted"
}

Write-Step "Release completed!" "Green"
Write-Host "🌐 View release: https://github.com/$(gh repo view --json owner,name -q '.owner.login + `"/`" + .name')/releases/tag/$tagName" -ForegroundColor Cyan 