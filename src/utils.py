import sys
import os
from pathlib import Path

def resource_path(relative_path: str) -> Path:
    """ PyInstaller 환경과 일반 환경 양쪽에서 리소스 파일의 절대 경로를 반환합니다. (읽기 전용) """
    try:
        # PyInstaller는 임시 폴더를 생성하고 _MEIPASS에 경로를 저장합니다.
        # 이 경로가 실행 파일이 압축 해제된 위치입니다.
        base_path = Path(sys._MEIPASS)
    except Exception:
        # PyInstaller로 빌드되지 않은 경우 (개발 환경)
        # 프로젝트 루트를 기준으로 파일 경로를 찾습니다.
        base_path = Path(__file__).parent.parent.resolve()

    return base_path / relative_path

def get_app_root() -> Path:
    """
    PyInstaller로 빌드된 환경과 일반 환경 모두에서
    애플리케이션의 루트 디렉토리(쓰기 가능한)를 반환합니다.
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # PyInstaller로 빌드된 경우, .exe 파일이 있는 실제 디렉토리
        return Path(sys.executable).parent
    else:
        # 일반 개발 환경의 경우, 프로젝트 루트 디렉토리
        return Path(__file__).parent.parent.resolve() 