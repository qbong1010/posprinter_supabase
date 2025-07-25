from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QMouseEvent
import logging

class CompactWidget(QWidget):
    """
    포스 PC용 작은 위젯 - Always on top 기능
    더블클릭 시 전체 GUI로 전환됨
    """
    # 시그널 정의
    expand_requested = Signal()  # 전체 GUI로 전환 요청
    
    def __init__(self, order_data_callback=None):
        super().__init__()
        self.order_data_callback = order_data_callback
        self.setup_ui()
        self.setup_update_timer()
        
    def setup_ui(self):
        """UI 설정"""
        # 윈도우 속성 설정
        self.setWindowTitle("주문 모니터")
        self.setFixedSize(250, 120)  # 고정 크기
        
        # Always on top 설정
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |  # 태스크바에서 숨김
            Qt.WindowType.FramelessWindowHint  # 프레임 없음
        )
        
        # 메인 레이아웃
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        
        # 제목 영역
        title_layout = QHBoxLayout()
        
        # 제목
        self.title_label = QLabel("📋 주문 모니터")
        self.title_label.setFont(QFont("맑은 고딕", 10, QFont.Weight.Bold))
        title_layout.addWidget(self.title_label)
        
        # 닫기 버튼 (최소화 대신 전체 GUI로 전환)
        self.expand_btn = QPushButton("⛶")
        self.expand_btn.setFixedSize(20, 20)
        self.expand_btn.setToolTip("전체 화면으로 전환")
        self.expand_btn.clicked.connect(self.expand_requested.emit)
        title_layout.addWidget(self.expand_btn)
        
        layout.addLayout(title_layout)
        
        # 주문 정보 영역
        info_layout = QVBoxLayout()
        
        # 대기 주문 수
        self.pending_orders_label = QLabel("대기 주문: 0개")
        self.pending_orders_label.setFont(QFont("맑은 고딕", 9))
        info_layout.addWidget(self.pending_orders_label)
        
        # 마지막 업데이트 시간
        self.last_update_label = QLabel("마지막 업데이트: 대기 중...")
        self.last_update_label.setFont(QFont("맑은 고딕", 8))
        self.last_update_label.setStyleSheet("color: #666;")
        info_layout.addWidget(self.last_update_label)
        
        # 상태 표시바
        self.status_bar = QProgressBar()
        self.status_bar.setVisible(False)  # 초기에는 숨김
        self.status_bar.setMaximumHeight(4)
        info_layout.addWidget(self.status_bar)
        
        layout.addLayout(info_layout)
        
        # 하단 정보
        bottom_layout = QHBoxLayout()
        
        self.auto_print_status = QLabel("🖨️ 자동출력: 확인중")
        self.auto_print_status.setFont(QFont("맑은 고딕", 7))
        self.auto_print_status.setStyleSheet("color: #888;")
        bottom_layout.addWidget(self.auto_print_status)
        
        bottom_layout.addStretch()
        
        # 더블클릭 안내
        help_label = QLabel("더블클릭으로 확장")
        help_label.setFont(QFont("맑은 고딕", 7))
        help_label.setStyleSheet("color: #aaa;")
        help_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        bottom_layout.addWidget(help_label)
        
        layout.addLayout(bottom_layout)
        
        # 전체 스타일 설정
        self.setStyleSheet("""
            QWidget {
                background-color: #2c3e50;
                color: white;
                border-radius: 8px;
            }
            QLabel {
                background: transparent;
                border: none;
            }
            QPushButton {
                background-color: #34495e;
                border: 1px solid #4a6741;
                border-radius: 3px;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4a6741;
            }
            QPushButton:pressed {
                background-color: #3d5a3d;
            }
            QProgressBar {
                border: none;
                background-color: #34495e;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background-color: #27ae60;
                border-radius: 2px;
            }
        """)
        
    def setup_update_timer(self):
        """데이터 업데이트 타이머 설정"""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_data)
        self.update_timer.start(5000)  # 5초마다 업데이트
        
    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """더블클릭 이벤트 - 전체 GUI로 전환"""
        if event.button() == Qt.MouseButton.LeftButton:
            logging.info("CompactWidget: 더블클릭으로 전체 GUI 모드 요청")
            self.expand_requested.emit()
        super().mouseDoubleClickEvent(event)
        
    def mousePressEvent(self, event: QMouseEvent):
        """마우스 드래그를 위한 위치 저장"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_position = event.globalPosition().toPoint()
        super().mousePressEvent(event)
        
    def mouseMoveEvent(self, event: QMouseEvent):
        """위젯 드래그 이동"""
        if hasattr(self, 'drag_start_position') and event.buttons() == Qt.MouseButton.LeftButton:
            diff = event.globalPosition().toPoint() - self.drag_start_position
            self.move(self.pos() + diff)
            self.drag_start_position = event.globalPosition().toPoint()
        super().mouseMoveEvent(event)
        
    def update_data(self):
        """주문 데이터 업데이트"""
        try:
            if self.order_data_callback:
                data = self.order_data_callback()
                self.update_display(data)
        except Exception as e:
            logging.error(f"CompactWidget 데이터 업데이트 오류: {e}")
            
    def update_display(self, data):
        """화면 표시 업데이트"""
        if not data:
            return
            
        # 대기 주문 수 업데이트
        pending_count = data.get('pending_orders', 0)
        self.pending_orders_label.setText(f"대기 주문: {pending_count}개")
        
        # 배경색 변경 (긴급도에 따라)
        if pending_count > 5:
            self.setStyleSheet(self.styleSheet().replace("#2c3e50", "#c0392b"))  # 빨간색
        elif pending_count > 2:
            self.setStyleSheet(self.styleSheet().replace("#2c3e50", "#f39c12"))  # 주황색
        else:
            self.setStyleSheet(self.styleSheet().replace("#c0392b", "#2c3e50").replace("#f39c12", "#2c3e50"))  # 기본색
            
        # 마지막 업데이트 시간
        from datetime import datetime
        current_time = datetime.now().strftime("%H:%M:%S")
        self.last_update_label.setText(f"마지막 업데이트: {current_time}")
        
        # 자동출력 상태
        auto_print = data.get('auto_print_enabled', False)
        status_text = "켜짐" if auto_print else "꺼짐"
        icon = "🖨️" if auto_print else "🚫"
        self.auto_print_status.setText(f"{icon} 자동출력: {status_text}")
        
    def show_loading(self, show=True):
        """로딩 상태 표시"""
        self.status_bar.setVisible(show)
        if show:
            self.status_bar.setRange(0, 0)  # 무한 프로그레스
        else:
            self.status_bar.setRange(0, 100)
            
    def closeEvent(self, event):
        """위젯 닫기 시 전체 GUI로 전환"""
        logging.info("CompactWidget: 닫기 요청 - 전체 GUI 모드로 전환")
        self.expand_requested.emit()
        event.ignore()  # 실제로는 숨기기만 함 