@echo off
REM 프로젝트 폴더로 이동합니다.
cd "C:\Users\POS\Desktop\posprinter_supabase"

REM 가상환경을 활성화합니다.
call ".\venv\Scripts\activate.bat"

REM 터미널 창 없이 메인 파이썬 스크립트를 실행합니다.
start "" pythonw main.py 