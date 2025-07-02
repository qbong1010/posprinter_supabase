@echo off
chcp 65001 >nul
cls

echo.
echo =================================
echo  POS 프린터 설치 프로그램 v1.2
echo =================================
echo.

:: 관리자 권한 확인 및 요청
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [!] 관리자 권한이 필요합니다.
    echo     UAC 프롬프트에서 '예'를 클릭하여 설치를 계속하세요.
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

:: PowerShell 스크립트 경로 설정
set "SCRIPT_PATH=%~dp0installer.ps1"

echo [*] 설치 스크립트를 확인하는 중...
echo    - 경로: %SCRIPT_PATH%
echo.

:: 설치 스크립트 존재 여부 확인
if not exist "%SCRIPT_PATH%" (
    echo [!] 오류: 설치 스크립트를 찾을 수 없습니다.
    echo     'installer.ps1' 파일이 있는지 확인하세요.
    echo.
    pause
    exit /b
)

echo [*] PowerShell 설치 프로그램을 시작합니다...
echo.

:: PowerShell 실행
powershell -ExecutionPolicy Bypass -File "%SCRIPT_PATH%"

echo.
echo =================================
echo  설치 과정이 종료되었습니다.
echo =================================
echo.
pause 