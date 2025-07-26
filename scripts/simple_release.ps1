# Simple Release Script for POS Printer
# Usage: .\simple_release.ps1 -Version "1.2.16" -Message "프린터 매니저 최적화"

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

function Write-Info($Message) {
    Write-Host "ℹ️  $Message" -ForegroundColor Yellow
}

Write-Step "POS Printer v$Version 간단 릴리즈 시작" "Green"

# 1. Git 상태 확인
Write-Step "Git 상태 확인 중..."
$gitStatus = git status --porcelain
if ($gitStatus) {
    Write-Info "변경사항이 있습니다:"
    git status --short
    Write-Host "`n변경사항을 커밋하시겠습니까? (y/N): " -NoNewline -ForegroundColor Yellow
    $response = Read-Host
    
    if ($response -match '^[yY]') {
        # 변경사항 요약 보기
        Write-Step "변경사항 요약:"
        git diff --stat
        
        # 커밋 진행
        git add .
        git commit -m $Message
        
        if ($LASTEXITCODE -eq 0) {
            Write-Success "변경사항이 커밋되었습니다."
        } else {
            Write-Error "커밋 실패"
        }
    } else {
        Write-Error "릴리즈를 진행하기 전에 변경사항을 커밋해주세요."
    }
} else {
    Write-Success "변경사항이 없습니다. 깨끗한 상태입니다."
}

# 2. version.json 업데이트
Write-Step "version.json 업데이트 중..."
$versionInfo = @{
    version = $Version
    build_date = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    description = "POS Printer Software"
    build_type = "Release"
}
$versionInfo | ConvertTo-Json -Depth 10 | Out-File -FilePath "version.json" -Encoding UTF8
Write-Success "version.json이 v$Version으로 업데이트되었습니다."

# 3. version.json 변경사항 커밋
git add version.json
git commit -m "Bump version to $Version"
if ($LASTEXITCODE -eq 0) {
    Write-Success "버전 업데이트가 커밋되었습니다."
} else {
    Write-Error "버전 업데이트 커밋 실패"
}

# 4. 원격 저장소에 푸시
Write-Step "원격 저장소에 푸시 중..."
git push origin main
if ($LASTEXITCODE -eq 0) {
    Write-Success "원격 저장소에 푸시 완료"
} else {
    Write-Error "푸시 실패"
}

# 5. Git 태그 생성 및 푸시
Write-Step "Git 태그 생성 중..."
$tagName = "v$Version"
try {
    git tag $tagName
    git push origin $tagName
    Write-Success "태그 '$tagName'이 생성되고 푸시되었습니다."
} catch {
    Write-Error "태그 생성 실패: $_"
}

# 6. GitHub CLI로 릴리즈 생성 (선택사항)
Write-Step "GitHub 릴리즈 생성 시도 중..."
try {
    gh --version | Out-Null
    
    $releaseNotes = @"
## POS Printer v$Version

### 변경사항
$Message

### 업데이트 방법
1. 프로젝트 디렉토리에서 다음 명령어 실행:
   ``git pull origin main``

2. 또는 Git GUI 도구를 사용하여 최신 변경사항을 받아옴

### 사용 방법
- 바탕화면의 'POS Printer' 바로가기를 통해 실행
- run.bat 파일을 직접 실행

빌드 일시: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
"@

    gh release create $tagName `
        --title "POS Printer v$Version" `
        --notes $releaseNotes
        
    Write-Success "GitHub 릴리즈가 생성되었습니다."
} catch {
    Write-Info "GitHub CLI를 사용할 수 없거나 오류가 발생했습니다. 수동으로 릴리즈를 생성하세요."
    Write-Info "태그는 이미 생성되었으므로 GitHub 웹사이트에서 릴리즈를 만들 수 있습니다."
}

# 7. 완료 메시지
Write-Step "릴리즈 완료!" "Green"
Write-Host ""
Write-Success "✨ POS Printer v$Version 릴리즈가 완료되었습니다!"
Write-Host ""
Write-Info "📌 업데이트 안내:"
Write-Host "   - 사용자는 프로젝트 디렉토리에서 'git pull origin main' 실행"
Write-Host "   - 또는 GitHub에서 최신 코드를 다운로드"
Write-Host ""
Write-Info "🔗 GitHub 태그: https://github.com/$(gh repo view --json owner,name -q '.owner.login + "/" + .name' 2>$null)/releases/tag/$tagName" 