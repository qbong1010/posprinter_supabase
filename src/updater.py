import os
import json
import requests
import zipfile
import shutil
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import sys

class AutoUpdater:
    def __init__(self, github_repo: str, current_version: str):
        """
        GitHub 자동 업데이트 시스템
        
        Args:
            github_repo: GitHub 저장소 (예: "username/repository")
            current_version: 현재 프로그램 버전
        """
        self.github_repo = github_repo
        self.current_version = current_version
        self.api_url = f"https://api.github.com/repos/{github_repo}"
        self.latest_version: Optional[str] = None
        
        # 업데이트 로거 설정
        self.logger = logging.getLogger("updater")
        handler = logging.FileHandler("update.log", encoding="utf-8")
        handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def check_for_updates(self) -> Optional[Dict[str, Any]]:
        """
        GitHub에서 최신 릴리즈 확인
        
        Returns:
            최신 릴리즈 정보 또는 None (업데이트가 없는 경우)
        """
        try:
            self.logger.info("업데이트 확인 중...")
            response = requests.get(f"{self.api_url}/releases/latest", timeout=10)
            response.raise_for_status()
            
            latest_release = response.json()
            latest_version = latest_release["tag_name"].lstrip("v")
            
            self.logger.info(f"현재 버전: {self.current_version}")
            self.logger.info(f"최신 버전: {latest_version}")
            
            if self._is_newer_version(latest_version, self.current_version):
                self.logger.info("새로운 업데이트가 있습니다.")
                self.latest_version = latest_version
                return latest_release
            else:
                self.logger.info("최신 버전을 사용 중입니다.")
                return None
                
        except requests.RequestException as e:
            self.logger.error(f"업데이트 확인 실패: {e}")
            return None
        except Exception as e:
            self.logger.error(f"업데이트 확인 중 오류 발생: {e}")
            return None
    
    def _is_newer_version(self, latest: str, current: str) -> bool:
        """버전 비교"""
        try:
            latest_parts = [int(x) for x in latest.split('.')]
            current_parts = [int(x) for x in current.split('.')]
            
            # 길이 맞추기
            max_len = max(len(latest_parts), len(current_parts))
            latest_parts.extend([0] * (max_len - len(latest_parts)))
            current_parts.extend([0] * (max_len - len(current_parts)))
            
            return latest_parts > current_parts
        except:
            return False
    
    def download_update(self, release_info: Dict[str, Any]) -> Optional[str]:
        """
        업데이트 파일 다운로드
        
        Args:
            release_info: GitHub 릴리즈 정보
            
        Returns:
            다운로드된 파일 경로 또는 None
        """
        try:
            # ZIP 파일 에셋 찾기
            zip_asset = None
            for asset in release_info.get("assets", []):
                if asset["name"].endswith(".zip"):
                    zip_asset = asset
                    break
            
            if not zip_asset:
                # 소스 코드 ZIP 사용
                download_url = release_info["zipball_url"]
                filename = f"update_{release_info['tag_name']}.zip"
            else:
                download_url = zip_asset["browser_download_url"]
                filename = zip_asset["name"]
            
            self.logger.info(f"업데이트 다운로드 중: {download_url}")
            
            # 실행 파일 위치를 기준으로 임시 폴더 경로 결정
            if getattr(sys, 'frozen', False):
                base_path = Path(sys.executable).parent
            else:
                base_path = Path(__file__).resolve().parent.parent

            # 임시 디렉토리에 다운로드
            temp_dir = base_path / "temp_update"
            temp_dir.mkdir(exist_ok=True)
            download_path = temp_dir / filename
            
            response = requests.get(download_url, stream=True, timeout=30)
            response.raise_for_status()
            
            with open(download_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            self.logger.info(f"다운로드 완료: {download_path}")
            return str(download_path)
            
        except Exception as e:
            self.logger.error(f"다운로드 실패: {e}")
            return None
    
    def apply_update(self, zip_path: str, backup: bool = True) -> bool:
        """
        업데이트 적용 (실행 파일 교체 방식)
        
        1. 임시 폴더에 압축 해제
        2. 업데이트용 배치 파일 생성
        3. 배치 파일 실행하여 현재 프로세스 종료 및 파일 교체
        
        Args:
            zip_path: 다운로드된 ZIP 파일 경로
            backup: 백업 생성 여부 (이 방식에서는 미사용)
            
        Returns:
            성공 시 배치파일 실행, 실패 시 False
        """
        try:
            # 실행 파일 위치를 기준으로 모든 경로를 결정
            if not getattr(sys, 'frozen', False):
                self.logger.error("이 업데이트 방식은 빌드된 실행 파일에서만 사용 가능합니다.")
                return False

            current_dir = Path(sys.executable).parent
            current_exe = Path(sys.executable)
            
            temp_dir = current_dir / "temp_update"
            extract_dir = temp_dir / "extracted"
            
            # 이전 압축 해제 폴더 정리
            if extract_dir.exists():
                self._safe_remove_tree(extract_dir)
            extract_dir.mkdir(parents=True, exist_ok=True)
            
            # ZIP 파일 압축 해제
            self.logger.info("업데이트 파일 압축 해제 중...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            # 압축 해제된 폴더에서 새 실행 파일 찾기
            # GitHub Release는 종종 repo-name-tag 폴더 안에 소스를 넣음
            new_exe_path = None
            possible_exe_names = [current_exe.name, "POSPrinter.exe"]
            
            # 최상위 디렉토리에서 먼저 찾아보기
            for name in possible_exe_names:
                if (extract_dir / name).exists():
                    new_exe_path = extract_dir / name
                    break
            
            # 하위 디렉토리에서도 찾아보기 (GitHub 소스코드 zip 대비)
            if not new_exe_path:
                for root, _, files in os.walk(extract_dir):
                    for file in files:
                        if file in possible_exe_names:
                            new_exe_path = Path(root) / file
                            break
                    if new_exe_path:
                        break

            if not new_exe_path:
                self.logger.error("압축 파일에서 새 실행 파일을 찾을 수 없습니다.")
                return False

            self.logger.info(f"새 실행 파일 위치: {new_exe_path}")

            # 업데이트용 배치 파일 생성
            updater_bat_path = current_dir / "update_runner.bat"
            
            # 실행중인 프로세스 ID 가져오기
            pid = os.getpid()

            # 배치 스크립트 내용
            # 1. 원본 프로세스가 종료될 때까지 대기 (taskkill이 즉시 종료되지 않을 수 있음)
            # 2. 기존 실행 파일을 .old로 이름 변경 (삭제 실패 대비)
            # 3. 새 실행 파일을 현재 위치로 복사
            # 4. 새 프로그램 실행
            # 5. 임시 파일(.old, .bat) 삭제 스크립트 실행 후 자신도 삭제
            batch_content = f"""@echo off
echo.
echo ===================================
echo   POS Printer 업데이트 진행 중...
echo ===================================
echo.
echo 이전 프로그램을 종료합니다 (PID: {pid})...
taskkill /PID {pid} /F > nul
:wait_loop
tasklist /FI "PID eq {pid}" | find "{pid}" > nul
if not errorlevel 1 (
    timeout /t 1 /nobreak > nul
    goto wait_loop
)
echo 프로그램이 종료되었습니다.
echo.

echo 파일을 교체합니다...
ren "{current_exe.name}" "{current_exe.name}.old"
copy /Y "{new_exe_path}" "{current_exe}"
echo 파일 교체 완료.
echo.

echo 새 버전을 실행합니다...
start "" "{current_exe}"

echo.
echo 임시 파일을 정리합니다...
(
    timeout /t 5 /nobreak > nul && 
    del "{current_exe.name}.old" > nul &&
    del "{updater_bat_path.name}" > nul
)
"""
            
            with open(updater_bat_path, 'w', encoding='utf-8') as f:
                f.write(batch_content)
                
            self.logger.info("업데이트 배치 파일 생성 완료. 프로그램을 종료하고 업데이트를 시작합니다.")
            
            # 생성된 배치 파일을 새 창에서 실행
            os.startfile(updater_bat_path)
            
            # 현재 프로그램 종료 (배치 파일이 이어받아 처리)
            sys.exit(0)

        except Exception as e:
            self.logger.error(f"업데이트 적용 실패: {e}")
            # 실패 시 백업 복원 시도 (필요 시 구현)
            return False
    
    def _safe_remove_tree(self, path: Path):
        """안전하게 디렉토리 트리 삭제 (권한 문제 해결)"""
        if not path.exists():
            return
            
        def handle_remove_readonly(func, path, exc):
            """읽기 전용 파일 삭제를 위한 오류 핸들러"""
            import stat
            if func in (os.unlink, os.remove) and exc[1].errno == 13:
                os.chmod(path, stat.S_IWRITE)
                func(path)
            else:
                raise exc[1]
        
        try:
            # __pycache__ 폴더와 .pyc 파일 먼저 정리
            for root, dirs, files in os.walk(path):
                # __pycache__ 폴더 찾아서 삭제
                if '__pycache__' in dirs:
                    pycache_path = Path(root) / '__pycache__'
                    try:
                        shutil.rmtree(pycache_path, onerror=handle_remove_readonly)
                        dirs.remove('__pycache__')
                    except:
                        pass
                
                # .pyc 파일 삭제
                for file in files:
                    if file.endswith('.pyc'):
                        try:
                            os.unlink(Path(root) / file)
                        except:
                            pass
            
            # 전체 트리 삭제
            shutil.rmtree(path, onerror=handle_remove_readonly)
            
        except Exception as e:
            self.logger.warning(f"디렉토리 삭제 중 오류: {path} - {e}")
    
    def _safe_copy_tree(self, src: Path, dst: Path):
        """안전하게 디렉토리 트리 복사 (캐시 폴더 제외)"""
        def ignore_cache_files(dir_path, contents):
            """캐시 파일들을 복사에서 제외"""
            ignored = []
            for item in contents:
                if item in ('__pycache__', '.pytest_cache', '.mypy_cache'):
                    ignored.append(item)
                elif item.endswith('.pyc'):
                    ignored.append(item)
            return ignored
        
        try:
            shutil.copytree(src, dst, ignore=ignore_cache_files)
        except Exception as e:
            self.logger.warning(f"디렉토리 복사 중 오류: {src} -> {dst} - {e}")
            raise
    
    def _restore_from_backup(self, backup_dir: Path):
        """백업에서 복원"""
        current_dir = Path.cwd()
        
        for item in backup_dir.iterdir():
            dest_path = current_dir / item.name
            
            if dest_path.exists():
                if dest_path.is_dir():
                    shutil.rmtree(dest_path)
                else:
                    dest_path.unlink()
            
            if item.is_dir():
                shutil.copytree(item, dest_path)
            else:
                shutil.copy2(item, dest_path)
    
    def _update_version_info(self):
        """버전 정보 파일 업데이트"""
        try:
            if not self.latest_version:
                self.logger.warning("최신 버전 정보가 없어 version.json 업데이트를 건너뜁니다.")
                return

            # 실행 파일 위치를 기준으로 경로 결정
            if getattr(sys, 'frozen', False):
                base_path = Path(sys.executable).parent
            else:
                base_path = Path(__file__).resolve().parent.parent

            version_file = base_path / "version.json"
            app_log_path = base_path / "app.log"

            version_info = {
                "version": self.latest_version,
                "updated_at": str(app_log_path.stat().st_mtime if app_log_path.exists() else 0)
            }
            
            with open(version_file, 'w', encoding='utf-8') as f:
                json.dump(version_info, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            self.logger.warning(f"버전 정보 업데이트 실패: {e}")

def get_current_version() -> str:
    """현재 프로그램 버전 가져오기"""
    try:
        # PyInstaller로 빌드되었을 때와 일반 실행 환경 모두 지원
        if getattr(sys, 'frozen', False):
            # 빌드된 .exe 파일의 경로
            base_path = Path(sys.executable).parent
        else:
            # 일반 .py 실행 환경의 경로
            base_path = Path(__file__).resolve().parent.parent

        version_file = base_path / "version.json"
        
        if version_file.exists():
            with open(version_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("version", "1.0.0")
    except Exception:
        # 오류 발생 시 기본 버전 반환 (예: 파일 권한 문제)
        pass
    
    return "1.0.0"

def check_and_update(github_repo: str, auto_apply: bool = False) -> bool:
    """
    업데이트 확인 및 적용
    
    Args:
        github_repo: GitHub 저장소
        auto_apply: 자동 적용 여부
        
    Returns:
        업데이트 적용 여부
    """
    current_version = get_current_version()
    updater = AutoUpdater(github_repo, current_version)
    
    # 업데이트 확인
    release_info = updater.check_for_updates()
    if not release_info:
        return False
    
    if not auto_apply:
        # 사용자 확인 필요
        print(f"새로운 업데이트가 있습니다: {release_info['tag_name']}")
        print(f"릴리즈 노트: {release_info.get('body', '없음')}")
        
        response = input("업데이트를 설치하시겠습니까? (y/N): ")
        if response.lower() not in ['y', 'yes', '예', 'ㅇ']:
            return False
    
    # 업데이트 다운로드 및 적용
    zip_path = updater.download_update(release_info)
    if not zip_path:
        return False
    
    return updater.apply_update(zip_path) 