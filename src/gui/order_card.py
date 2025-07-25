from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QFrame, QSizePolicy, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPalette
from datetime import datetime
import logging


class OrderCard(QFrame):
    """개별 주문을 카드 형식으로 표시하는 위젯"""
    
    # 시그널 정의
    order_approved = Signal(int)  # 주문 승인 시그널 (order_id)
    order_printed = Signal(int)   # 주문 출력 시그널 (order_id)
    
    def __init__(self, order_data, parent=None):
        super().__init__(parent)
        self.order_data = order_data
        self.order_id = order_data.get("order_id")
        self.setup_ui()
        self.update_card_style()
        
    def setup_ui(self):
        """카드 UI를 설정합니다."""
        self.setFrameStyle(QFrame.Box)
        self.setLineWidth(1)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(180)
        
        # 메인 레이아웃
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)
        
        # 헤더 레이아웃 (주문번호 + 승인 상태)
        header_layout = QHBoxLayout()
        
        # 주문번호
        self.order_number_label = QLabel(f"주문 #{self.order_id}")
        font = QFont()
        font.setBold(True)
        font.setPointSize(14)
        self.order_number_label.setFont(font)
        header_layout.addWidget(self.order_number_label)
        
        header_layout.addStretch()
        
        # 승인 상태 표시
        self.approval_status_label = QLabel()
        header_layout.addWidget(self.approval_status_label)
        
        main_layout.addLayout(header_layout)
        
        # 회사명
        company_name = self.order_data.get("company_name", "N/A")
        self.company_label = QLabel(f"📍 {company_name}")
        font = QFont()
        font.setPointSize(12)
        self.company_label.setFont(font)
        main_layout.addWidget(self.company_label)
        
        # 메뉴 정보
        self.menu_label = QLabel()
        self.update_menu_text()
        font = QFont()
        font.setPointSize(10)
        self.menu_label.setFont(font)
        self.menu_label.setWordWrap(True)
        main_layout.addWidget(self.menu_label)
        
        # 하단 정보 레이아웃
        bottom_layout = QHBoxLayout()
        
        # 주문 시간
        created_at = self.order_data.get("created_at", "")
        formatted_time = self.format_time(created_at)
        self.time_label = QLabel(f"🕒 {formatted_time}")
        font = QFont()
        font.setPointSize(10)
        self.time_label.setFont(font)
        bottom_layout.addWidget(self.time_label)
        
        bottom_layout.addStretch()
        
        # 총액
        total_price = self.order_data.get("total_price", 0)
        self.price_label = QLabel(f"💰 {total_price:,}원")
        font = QFont()
        font.setBold(True)
        font.setPointSize(11)
        self.price_label.setFont(font)
        bottom_layout.addWidget(self.price_label)
        
        main_layout.addLayout(bottom_layout)
        
        # 버튼 레이아웃
        button_layout = QHBoxLayout()
        
        # 승인 버튼
        self.approve_btn = QPushButton("승인")
        self.approve_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)
        self.approve_btn.clicked.connect(self.on_approve_clicked)
        button_layout.addWidget(self.approve_btn)
        
        # 출력 버튼
        self.print_btn = QPushButton("출력")
        self.print_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:pressed {
                background-color: #004085;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)
        self.print_btn.clicked.connect(self.on_print_clicked)
        button_layout.addWidget(self.print_btn)
        
        button_layout.addStretch()
        
        main_layout.addLayout(button_layout)
        
        # 모든 UI 요소가 생성된 후 상태 업데이트
        self.update_approval_status()
        
    def update_menu_text(self):
        """메뉴 텍스트를 업데이트합니다."""
        items = self.order_data.get("items", [])
        if not items:
            self.menu_label.setText("🍽️ 메뉴 정보 없음")
            return
            
        menu_texts = []
        for item in items[:3]:  # 최대 3개까지만 표시
            name = item.get("name", "N/A")
            quantity = item.get("quantity", 1)
            menu_texts.append(f"• {name} x{quantity}")
        
        if len(items) > 3:
            menu_texts.append(f"• ... 외 {len(items) - 3}개")
            
        self.menu_label.setText("🍽️ " + "\n".join(menu_texts))
        
    def update_approval_status(self):
        """승인 상태를 업데이트합니다."""
        is_approved = self.order_data.get("is_approved", False)
        if is_approved:
            self.approval_status_label.setText("✅ 승인됨")
            self.approval_status_label.setStyleSheet("color: #28a745; font-weight: bold;")
            self.approve_btn.setEnabled(False)
            self.approve_btn.setText("승인완료")
        else:
            self.approval_status_label.setText("⏳ 승인대기")
            self.approval_status_label.setStyleSheet("color: #ffc107; font-weight: bold;")
            self.approve_btn.setEnabled(True)
            self.approve_btn.setText("승인")
            
    def update_card_style(self):
        """카드 스타일을 주문 상태에 따라 업데이트합니다."""
        is_printed = self.order_data.get("is_printed", False)
        is_approved = self.order_data.get("is_approved", False)
        
        if is_printed:
            # 출력 완료 - 연한 녹색
            self.setStyleSheet("""
                QFrame {
                    background-color: #d4edda;
                    border: 2px solid #28a745;
                    border-radius: 8px;
                }
            """)
        elif is_approved:
            # 승인됨 - 연한 파란색
            self.setStyleSheet("""
                QFrame {
                    background-color: #cce7ff;
                    border: 2px solid #007bff;
                    border-radius: 8px;
                }
            """)
        else:
            # 신규 주문 - 연한 노란색
            self.setStyleSheet("""
                QFrame {
                    background-color: #fff3cd;
                    border: 2px solid #ffc107;
                    border-radius: 8px;
                }
            """)
            
    def format_time(self, created_at):
        """시간을 포맷팅합니다."""
        if not created_at:
            return "시간 정보 없음"
            
        try:
            # ISO 형식의 날짜를 한국 시간으로 변환
            from datetime import datetime, timezone
            from zoneinfo import ZoneInfo
            
            dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            dt = dt.astimezone(ZoneInfo("Asia/Seoul"))
            return dt.strftime("%H:%M")
        except Exception as e:
            logging.error(f"시간 포맷팅 오류: {e}")
            return created_at[:16] if len(created_at) > 16 else created_at
            
    def on_approve_clicked(self):
        """승인 버튼이 클릭되었을 때 처리합니다."""
        reply = QMessageBox.question(
            self,
            "주문 승인",
            f"주문 #{self.order_id}를 승인하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        
        if reply == QMessageBox.Yes:
            # 로컬 데이터 업데이트
            self.order_data["is_approved"] = True
            self.order_data["approved_at"] = datetime.now().isoformat()
            self.order_data["approved_by"] = "매장직원"  # 추후 로그인 시스템 구현 시 실제 사용자명 사용
            
            # UI 업데이트
            self.update_approval_status()
            self.update_card_style()
            
            # 시그널 발생
            self.order_approved.emit(self.order_id)
            
    def on_print_clicked(self):
        """출력 버튼이 클릭되었을 때 처리합니다."""
        # 시그널 발생
        self.order_printed.emit(self.order_id)
        
    def update_order_data(self, new_data):
        """주문 데이터를 업데이트하고 UI를 새로고침합니다."""
        self.order_data = new_data
        self.update_approval_status()
        self.update_card_style()
        
        # 출력 상태에 따른 버튼 상태 업데이트
        is_printed = new_data.get("is_printed", False)
        if is_printed:
            self.print_btn.setEnabled(False)
            self.print_btn.setText("출력완료")
        else:
            self.print_btn.setEnabled(True)
            self.print_btn.setText("출력") 