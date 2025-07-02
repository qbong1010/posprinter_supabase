@echo off
chcp 65001 >nul 2>&1
title POS Printer Setup
cls

REM PowerShell 64비트 실행 파일 경로 확인 (32/64비트 호환)
SET "POWERSHELL_EXE=powershell.exe"
IF EXIST "%WINDIR%\sysnative\WindowsPowerShell\v1.0\powershell.exe" (
    SET "POWERSHELL_EXE=%WINDIR%\sysnative\WindowsPowerShell\v1.0\powershell.exe"
)

echo.
echo 🖨️ POS 프린터 간편 설치를 시작합니다...
echo.

REM 관리자 권한 확인
net session >nul 2>&1
if %errorLevel% == 0 (
    echo ✅ 관리자 권한으로 실행 중입니다.
    goto :start_build
) else (
    echo 🔐 관리자 권한이 필요합니다.
    echo 📁 현재 폴더: %~dp0
    echo.
    echo ⏳ UAC 창이 나타나면 "예"를 클릭해주세요...
    echo.
    
    REM 관리자 권한으로 재실행 (작업 디렉토리 설정)
    %POWERSHELL_EXE% -Command "Start-Process '%~f0' -Verb RunAs -WorkingDirectory '%~dp0'"
    exit /b
)

:start_build
echo.
echo 📂 배치 파일 위치: %~dp0
echo 📂 현재 작업 디렉토리: %CD%

REM 배치 파일이 있는 디렉토리로 이동
cd /d "%~dp0"
echo ✅ 프로젝트 폴더로 이동했습니다: %CD%
echo.

REM PowerShell 실행 정책 설정
echo 🔧 PowerShell 실행 정책을 설정합니다...
%POWERSHELL_EXE% -Command "Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force" 2>nul

REM build.ps1 실행 (빌드와 설치가 통합됨)
echo.
echo 🚀 빌드 및 설치 스크립트를 실행합니다...
echo.

if exist "build.ps1" (
    %POWERSHELL_EXE% -ExecutionPolicy Bypass -File "build.ps1"
    if %errorlevel% neq 0 (
        echo.
        echo ❌ 빌드 또는 설치 중 오류가 발생했습니다.
        echo.
        goto :manual_guide
    )
) else (
    echo ❌ build.ps1 파일을 찾을 수 없습니다.
    echo 📁 현재 폴더에 build.ps1 파일이 있는지 확인해주세요.
    echo.
    goto :manual_guide
)

echo.
echo ✅ 모든 과정이 완료되었습니다!
echo.

pause
exit /b

:manual_guide
echo.
echo 🔧 수동 실행 방법:
echo 1. 시작 메뉴에서 "PowerShell" 검색
echo 2. 우클릭 → "관리자 권한으로 실행"
echo 3. 다음 명령들을 순서대로 입력:
echo.
echo    Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
echo    cd "%~dp0"
echo    .\build.ps1
echo.
echo 📁 프로젝트 폴더 경로: %~dp0
echo.
pause
exit /b 