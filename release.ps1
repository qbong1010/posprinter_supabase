# 완전 자동화 릴리즈 스크립트
# 사용법: .\release.ps1 -Version "1.2.1" -Message "새로운 기능 추가"

param(
    [Parameter(Mandatory=$true)]
    [string]$Version,
    
    [Parameter(Mandatory=$false)]
    [string]$Message = "Release v$Version"
)

# UTF-8 인코딩 설정
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

# GitHub CLI 확인
try {
    gh --version | Out-Null
} catch {
    Write-Error "GitHub CLI가 설치되어 있지 않습니다. 'gh' 명령어를 사용할 수 없습니다."
}

Write-Step "POS Printer v$Version 릴리즈 시작"

# 1. Git 상태 확인
Write-Step "Git 상태 확인 중..."
$gitStatus = git status --porcelain
if ($gitStatus) {
    Write-Host "변경사항이 있습니다. 커밋하시겠습니까? (y/N): " -NoNewline -ForegroundColor Yellow
    $response = Read-Host
    if ($response -match '^[yY]') {
        git add .
        git commit -m $Message
        git push origin main
        Write-Success "변경사항이 커밋되었습니다."
    } else {
        Write-Error "릴리즈를 진행하기 전에 변경사항을 커밋해주세요."
    }
}

# 2. 버전 정보 업데이트
Write-Step "version.json 업데이트 중..."
$versionInfo = @{
    version = $Version
    build_date = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    description = "POS Printer Software"
    build_type = "Release"
}
$versionInfo | ConvertTo-Json -Depth 10 | Out-File -FilePath "version.json" -Encoding UTF8
Write-Success "version.json 업데이트 완료"

# 3. 빌드 실행
Write-Step "애플리케이션 빌드 중..."
try {
    .\build_clean.ps1 -Version $Version -OutputPath ".\release"
    Write-Success "빌드 완료"
} catch {
    Write-Error "빌드 실패: $_"
}

# 4. 압축 파일 생성
Write-Step "릴리즈 파일 압축 중..."
$zipName = "POSPrinter_v$Version.zip"
if (Test-Path $zipName) {
    Remove-Item $zipName -Force
}
Compress-Archive -Path ".\release\*" -DestinationPath $zipName -Force
Write-Success "압축 완료: $zipName"

# 5. Git 태그 생성 및 푸시
Write-Step "Git 태그 생성 중..."
$tagName = "v$Version"
try {
    git tag $tagName
    git push origin $tagName
    Write-Success "태그 생성 및 푸시 완료: $tagName"
} catch {
    Write-Error "태그 생성 실패: $_"
}

# 6. GitHub 릴리즈 생성
Write-Step "GitHub 릴리즈 생성 중..."
try {
    $releaseNotes = @"
## POS Printer v$Version

### 변경사항
$Message

### 설치 방법
1. 첨부된 ZIP 파일을 다운로드하세요
2. 압축을 해제하세요  
3. ``간편설치.bat``을 관리자 권한으로 실행하세요

### 업데이트 방법
- 기존 사용자: 프로그램 내 '업데이트 확인' 버튼 클릭
- 자동으로 다운로드 및 설치됩니다

### 시스템 요구사항
- Windows 10 이상
- 관리자 권한 (설치 시에만)

빌드 날짜: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
"@

    gh release create $tagName $zipName `
        --title "POS Printer v$Version" `
        --notes $releaseNotes
        
    Write-Success "GitHub 릴리즈 생성 완료"
} catch {
    Write-Error "GitHub 릴리즈 생성 실패: $_"
}

# 7. 정리
Write-Step "정리 작업 중..."
if (Test-Path $zipName) {
    Remove-Item $zipName -Force
    Write-Success "임시 압축 파일 삭제"
}

Write-Step "릴리즈 완료!" "Green"
Write-Host "🌐 릴리즈 확인: https://github.com/$(gh repo view --json owner,name -q '.owner.login + `"/`" + .name')/releases/tag/$tagName" -ForegroundColor Cyan 