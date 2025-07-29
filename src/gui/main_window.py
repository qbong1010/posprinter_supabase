from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QTabWidget, QTextEdit, QPushButton, QHBoxLayout, QMessageBox
from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtGui import QFont
from src.gui.order_widget import OrderWidget
from src.gui.printer_widget import PrinterWidget
from src.supabase_client import SupabaseClient
from src.gui.receipt_preview import read_receipt_file
from src.updater import check_and_update, get_current_version
from src.error_logger import get_error_logger
import os
import logging
import subprocess
import sys



class ReceiptPreviewWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        
        # 미리보기 텍스트 영역
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setFont(QFont("Courier New", 10))  # 고정폭 폰트 사용
        
        # 새로고침 버튼
        refresh_btn = QPushButton("새로고침")
        refresh_btn.clicked.connect(self.refresh_preview)
        
        layout.addWidget(refresh_btn)
        layout.addWidget(self.preview_text)
        
        # 초기 미리보기 로드
        self.refresh_preview()
        
    def refresh_preview(self):
        preview_text = read_receipt_file()
        if preview_text:
            self.preview_text.setText(preview_text)
        else:
            self.preview_text.setText("영수증 미리보기를 불러올 수 없습니다.")

class MainWindow(QMainWindow):
    def __init__(self, supabase_config, db_config):
        super().__init__()
        self.setWindowTitle("주문 관리 시스템")
        self.setMinimumSize(800, 600)
        
        # WindowManager는 나중에 설정됨 (main.py에서)
        self.window_manager = None
        
        # 중앙 위젯 설정
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 메인 레이아웃 설정
        layout = QVBoxLayout(central_widget)
        
        # 상단 버튼 영역 추가
        button_layout = QHBoxLayout()
        
        # 현재 버전 표시
        current_version = get_current_version()
        version_label = QPushButton(f"버전: {current_version}")
        version_label.setEnabled(False)
        version_label.setStyleSheet("background-color: #e1e1e1; color: #333;")
        
        # 위젯 모드 버튼 추가
        self.compact_mode_btn = QPushButton("📱 위젯 모드")
        self.compact_mode_btn.setToolTip("작은 위젯으로 전환 (Always on top)")
        self.compact_mode_btn.clicked.connect(self.switch_to_compact_mode)
        self.compact_mode_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #229954;
            }
            QPushButton:pressed {
                background-color: #1e8449;
            }
        """)
        
        # 업데이트 버튼
        self.update_btn = QPushButton("업데이트")
        self.update_btn.clicked.connect(self.update_from_git)
        self.update_btn.setStyleSheet("""
            QPushButton {
                background-color: #17A2B8;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #138496;
            }
            QPushButton:pressed {
                background-color: #117A8B;
            }
        """)
        
        button_layout.addWidget(version_label)
        button_layout.addStretch()
        button_layout.addWidget(self.compact_mode_btn)
        button_layout.addWidget(self.update_btn)
        
        layout.addLayout(button_layout)
        
        # 탭 위젯 생성
        tab_widget = QTabWidget()
        
        # 주문 관리 탭
        self.order_widget = OrderWidget(supabase_config, db_config)
        tab_widget.addTab(self.order_widget, "주문 관리")
        
        # 프린터 설정 탭
        self.printer_widget = PrinterWidget()
        tab_widget.addTab(self.printer_widget, "프린터 설정")
        
        # 영수증 미리보기 탭
        self.receipt_preview = ReceiptPreviewWidget()
        tab_widget.addTab(self.receipt_preview, "영수증 미리보기")
        
        layout.addWidget(tab_widget)

        # SupabaseClient 연결
        self.supabase_client = SupabaseClient()
        
        # 윈도우 설정
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f0f0;
            }
            QTabWidget::pane {
                border: 1px solid #cccccc;
                background: white;
            }
            QTabBar::tab {
                background: #e1e1e1;
                border: 1px solid #cccccc;
                padding: 8px 12px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: white;
                border-bottom-color: white;
            }
            QTabBar::tab:hover {
                background: #f0f0f0;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #cccccc;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px 0 3px;
            }
            QPushButton {
                background-color: #4a90e2;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #357abd;
            }
            QPushButton:pressed {
                background-color: #2a5f96;
            }
        """)
    
    @Slot()
    def update_from_git(self):
        """Git 저장소에서 최신 코드를 가져와 업데이트합니다."""
        try:
            # 확인 팝업 표시
            reply = QMessageBox.question(
                self,
                "업데이트 확인",
                "Git 저장소에서 최신 코드를 가져오시겠습니까?\n\n※ 로컬 변경사항이 있다면 덮어씌워질 수 있습니다.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply != QMessageBox.Yes:
                return
            
            # 버튼 상태 변경
            original_text = self.update_btn.text()
            self.update_btn.setText("업데이트 중...")
            self.update_btn.setEnabled(False)
            
            logging.info("Git 업데이트 시작")
            
            # 현재 작업 디렉토리 가져오기 (프로젝트 루트)
            current_dir = os.getcwd()
            logging.info(f"현재 작업 디렉토리: {current_dir}")
            
            # Git 상태 확인
            git_status_result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=current_dir,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if git_status_result.returncode == 0 and git_status_result.stdout.strip():
                # 로컬 변경사항이 있는 경우 추가 확인
                dirty_reply = QMessageBox.question(
                    self,
                    "로컬 변경사항 발견",
                    f"다음 파일들에 변경사항이 있습니다:\n\n{git_status_result.stdout}\n\n계속 진행하면 변경사항이 손실될 수 있습니다. 계속하시겠습니까?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if dirty_reply != QMessageBox.Yes:
                    return
            
            # git pull 실행
            logging.info("git pull 실행 중...")
            result = subprocess.run(
                ["git", "pull"],
                cwd=current_dir,
                capture_output=True,
                text=True,
                timeout=60  # 60초 타임아웃
            )
            
            if result.returncode == 0:
                # 성공
                output = result.stdout.strip()
                logging.info(f"Git 업데이트 성공: {output}")
                
                if "Already up to date" in output or "이미 최신입니다" in output:
                    # 이미 최신 버전
                    QMessageBox.information(
                        self, 
                        "업데이트 완료", 
                        "이미 최신 버전을 사용 중입니다."
                    )
                else:
                    # 업데이트됨 - 재시작 옵션 제공
                    restart_reply = QMessageBox.question(
                        self,
                        "업데이트 완료",
                        f"업데이트가 완료되었습니다.\n\n변경사항:\n{output}\n\n변경사항을 적용하려면 프로그램을 재시작해야 합니다. 지금 재시작하시겠습니까?",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.Yes
                    )
                    
                    if restart_reply == QMessageBox.Yes:
                        # 프로그램 재시작
                        self.restart_application()
            else:
                # 실패
                error_output = result.stderr.strip() or result.stdout.strip()
                logging.error(f"Git 업데이트 실패: {error_output}")
                
                QMessageBox.critical(
                    self,
                    "업데이트 실패",
                    f"Git 업데이트에 실패했습니다.\n\n오류 내용:\n{error_output}\n\n네트워크 연결이나 Git 설정을 확인해주세요."
                )
                
        except subprocess.TimeoutExpired:
            logging.error("Git 업데이트 타임아웃")
            QMessageBox.critical(self, "업데이트 실패", "업데이트 요청이 시간 초과되었습니다.\n네트워크 연결을 확인해주세요.")
            
        except FileNotFoundError:
            logging.error("Git 명령어를 찾을 수 없음")
            QMessageBox.critical(self, "업데이트 실패", "Git이 설치되어 있지 않거나 PATH에 등록되어 있지 않습니다.\n\nGit을 설치하고 PATH에 추가한 후 다시 시도해주세요.")
            
        except Exception as e:
            logging.error(f"Git 업데이트 중 예상치 못한 오류: {e}")
            QMessageBox.critical(self, "업데이트 실패", f"업데이트 중 오류가 발생했습니다:\n\n{str(e)}")
            
            # Supabase에도 에러 로깅
            error_logger = get_error_logger()
            if error_logger:
                error_logger.log_error(e, "Git 업데이트 오류", {"context": "git_update"})
        
        finally:
            # 버튼 상태 복원
            self.update_btn.setText(original_text)
            self.update_btn.setEnabled(True)

    def restart_application(self):
        """애플리케이션을 재시작합니다."""
        try:
            logging.info("애플리케이션 재시작 중...")
            
            # 현재 실행 중인 파일의 경로를 가져옴
            if getattr(sys, 'frozen', False):
                # PyInstaller로 빌드된 실행 파일
                executable = sys.executable
            else:
                # Python 스크립트로 실행 중
                executable = sys.executable
                script_path = os.path.abspath(sys.argv[0])
            
            # 새 프로세스 시작
            if getattr(sys, 'frozen', False):
                # 실행 파일인 경우
                subprocess.Popen([executable])
            else:
                # Python 스크립트인 경우
                subprocess.Popen([executable, script_path])
            
            # 현재 프로그램 종료
            sys.exit(0)
            
        except Exception as e:
            logging.error(f"애플리케이션 재시작 실패: {e}")
            QMessageBox.critical(
                self,
                "재시작 실패", 
                f"자동 재시작에 실패했습니다.\n수동으로 프로그램을 재시작해주세요.\n\n오류: {str(e)}"
            )
    
    def set_window_manager(self, window_manager):
        """WindowManager 설정"""
        self.window_manager = window_manager
        logging.info("MainWindow에 WindowManager 설정 완료")
    
    def switch_to_compact_mode(self):
        """위젯 모드로 전환"""
        try:
            if self.window_manager:
                logging.info("사용자가 위젯 모드 전환 요청")
                self.window_manager.switch_to_compact_mode()
            else:
                QMessageBox.warning(self, "오류", "위젯 모드 전환 기능이 초기화되지 않았습니다.")
                logging.error("WindowManager가 설정되지 않음")
        except Exception as e:
            logging.error(f"위젯 모드 전환 중 오류: {e}")
            QMessageBox.critical(self, "오류", f"위젯 모드 전환 중 오류가 발생했습니다:\n{e}")
            
    def closeEvent(self, event):
        """윈도우 닫기 이벤트 - WindowManager 정리"""
        try:
            if self.window_manager:
                self.window_manager.cleanup()
                logging.info("MainWindow 종료 시 WindowManager 정리 완료")
        except Exception as e:
            logging.error(f"WindowManager 정리 중 오류: {e}")
        
        super().closeEvent(event) 