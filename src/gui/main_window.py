from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QTabWidget, QTextEdit, QPushButton, QHBoxLayout, QMessageBox
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
from src.gui.order_widget import OrderWidget
from src.gui.printer_widget import PrinterWidget
from src.supabase_client import SupabaseClient
from src.gui.receipt_preview import read_receipt_file
from src.updater import check_and_update, get_current_version
import os
import logging

class UpdateCheckThread(QThread):
    """업데이트 확인을 위한 스레드"""
    update_available = Signal(dict)  # 업데이트 정보
    no_update = Signal()
    error = Signal(str)
    
    def __init__(self, github_repo):
        super().__init__()
        self.github_repo = github_repo
    
    def run(self):
        try:
            from src.updater import AutoUpdater, get_current_version
            current_version = get_current_version()
            updater = AutoUpdater(self.github_repo, current_version)
            
            release_info = updater.check_for_updates()
            if release_info:
                self.update_available.emit(release_info)
            else:
                self.no_update.emit()
        except Exception as e:
            self.error.emit(str(e))

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
        
        # GitHub 저장소 설정
        self.github_repo = os.getenv('GITHUB_REPO', 'qbong1010/posprinter_supabase')
        
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
        
        # 업데이트 확인 버튼
        self.update_btn = QPushButton("업데이트 확인")
        self.update_btn.clicked.connect(self.check_for_updates)
        
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
        
        # 업데이트 확인 스레드
        self.update_thread = None
        
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
    
    def check_for_updates(self):
        """업데이트 확인 버튼 클릭 시 호출"""
        try:
            if self.update_thread and self.update_thread.isRunning():
                QMessageBox.information(self, "업데이트 확인", "이미 업데이트를 확인 중입니다.")
                return
            
            self.update_btn.setText("확인 중...")
            self.update_btn.setEnabled(False)
            
            # 업데이트 확인 스레드 시작
            self.update_thread = UpdateCheckThread(self.github_repo)
            self.update_thread.update_available.connect(self.on_update_available)
            self.update_thread.no_update.connect(self.on_no_update)
            self.update_thread.error.connect(self.on_update_error)
            self.update_thread.finished.connect(self.on_update_check_finished)
            self.update_thread.start()
            
        except Exception as e:
            logging.error(f"업데이트 확인 중 오류: {e}")
            QMessageBox.critical(self, "오류", f"업데이트 확인 중 오류가 발생했습니다:\n{e}")
            self.on_update_check_finished()
    
    def on_update_available(self, release_info):
        """업데이트가 있을 때 호출"""
        try:
            version = release_info.get('tag_name', '알 수 없음')
            description = release_info.get('body', '업데이트 정보가 없습니다.')
            
            msg = QMessageBox(self)
            msg.setWindowTitle("업데이트 발견")
            msg.setIcon(QMessageBox.Information)
            msg.setText(f"새로운 버전이 있습니다: {version}")
            msg.setDetailedText(f"릴리즈 노트:\n{description}")
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg.setDefaultButton(QMessageBox.Yes)
            msg.button(QMessageBox.Yes).setText("업데이트 설치")
            msg.button(QMessageBox.No).setText("나중에")
            
            if msg.exec() == QMessageBox.Yes:
                self.apply_update(release_info)
            
        except Exception as e:
            logging.error(f"업데이트 알림 표시 중 오류: {e}")
            QMessageBox.critical(self, "오류", f"업데이트 정보 표시 중 오류가 발생했습니다:\n{e}")
    
    def on_no_update(self):
        """업데이트가 없을 때 호출"""
        QMessageBox.information(self, "업데이트 확인", "현재 최신 버전을 사용 중입니다.")
    
    def on_update_error(self, error_msg):
        """업데이트 확인 중 오류 발생 시 호출"""
        logging.error(f"업데이트 확인 오류: {error_msg}")
        QMessageBox.warning(self, "업데이트 확인 실패", f"업데이트 확인 중 오류가 발생했습니다:\n{error_msg}")
    
    def on_update_check_finished(self):
        """업데이트 확인 완료 시 호출"""
        self.update_btn.setText("업데이트 확인")
        self.update_btn.setEnabled(True)
    
    def apply_update(self, release_info):
        """업데이트 적용"""
        try:
            from src.updater import AutoUpdater, get_current_version
            
            current_version = get_current_version()
            updater = AutoUpdater(self.github_repo, current_version)
            
            # 다운로드 진행
            QMessageBox.information(self, "업데이트", "업데이트를 다운로드하고 있습니다.\n잠시만 기다려주세요.")
            
            zip_path = updater.download_update(release_info)
            if not zip_path:
                QMessageBox.critical(self, "업데이트 실패", "업데이트 다운로드에 실패했습니다.")
                return
            
            # 업데이트 적용
            if updater.apply_update(zip_path):
                msg = QMessageBox(self)
                msg.setWindowTitle("업데이트 완료")
                msg.setIcon(QMessageBox.Information)
                msg.setText("업데이트가 성공적으로 완료되었습니다.")
                msg.setInformativeText("프로그램을 다시 시작해주세요.")
                msg.setStandardButtons(QMessageBox.Ok)
                msg.exec()
                
                # 프로그램 종료
                self.close()
            else:
                QMessageBox.critical(self, "업데이트 실패", "업데이트 적용에 실패했습니다.\n백업이 복원되었습니다.")
                
        except Exception as e:
            logging.error(f"업데이트 적용 중 오류: {e}")
            QMessageBox.critical(self, "업데이트 오류", f"업데이트 중 오류가 발생했습니다:\n{e}")
    
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