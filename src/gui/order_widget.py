from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QLabel,
    QMessageBox,
    QProgressBar,
    QCheckBox,
    QComboBox,
)
from PySide6.QtCore import Qt, Slot, QTimer
import logging
import sqlite3
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Use an absolute import so this module works when executed directly.
from src.database.cache import SupabaseCache
from src.error_logger import get_error_logger

from src.printer.manager import PrinterManager
from src.gui.monitoring_factory import create_optimized_order_monitor

class OrderWidget(QWidget):
    def __init__(self, supabase_config, db_config):
        super().__init__()
        self.printer_manager = PrinterManager()
        self.cache = SupabaseCache(db_path=db_config['path'], supabase_config=supabase_config)
        self.cache.setup_sqlite()
        self.setup_ui()
        self.orders = []

        # 최적화된 모니터링 시스템 생성
        self.order_monitor = create_optimized_order_monitor(self, supabase_config, db_config)
        
        # 메시지 표시를 위한 타이머
        self.message_timer = QTimer()
        self.message_timer.setSingleShot(True)
        self.message_timer.timeout.connect(self.clear_temporary_message)

        # 초기 주문 로드
        self.refresh_orders()
        
        # 프로그램 시작 후 체크박스 상태 동기화
        self.sync_auto_print_checkbox()
        
        # 최적화된 모니터링 시작
        if self.order_monitor:
            self.order_monitor.start_monitoring()
        
    def setup_ui(self):
        # 메인 레이아웃
        layout = QVBoxLayout(self)
        
        # 상단 레이아웃 (제목 + 버튼)
        top_layout = QHBoxLayout()
        title_label = QLabel("식권 주문 현황")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        top_layout.addWidget(title_label)
        
        # 자동 출력 체크박스 추가
        self.auto_print_checkbox = QCheckBox("자동 출력")
        
        # 초기 상태 설정 및 로깅
        initial_auto_print_state = self.printer_manager.is_auto_print_enabled()
        logging.info(f"GUI 초기화: 자동 출력 설정 상태 = {initial_auto_print_state}")
        
        self.auto_print_checkbox.setChecked(initial_auto_print_state)
        self.auto_print_checkbox.stateChanged.connect(self.toggle_auto_print)
        top_layout.addWidget(self.auto_print_checkbox)
        
        self.refresh_btn = QPushButton("새로고침")
        self.refresh_btn.clicked.connect(self.refresh_orders)
        top_layout.addWidget(self.refresh_btn)

        self.sync_btn = QPushButton("데이터 동기화")
        self.sync_btn.clicked.connect(self.sync_static_tables)
        top_layout.addWidget(self.sync_btn)

        # 영수증 출력 버튼들
        self.print_customer_btn = QPushButton("손님 영수증")
        self.print_customer_btn.clicked.connect(self.print_customer_receipt)
        top_layout.addWidget(self.print_customer_btn)

        self.print_kitchen_btn = QPushButton("주방 영수증")
        self.print_kitchen_btn.clicked.connect(self.print_kitchen_receipt)
        top_layout.addWidget(self.print_kitchen_btn)

        self.print_both_btn = QPushButton("동시 출력")
        self.print_both_btn.clicked.connect(self.print_both_receipts)
        self.print_both_btn.setStyleSheet("""
            QPushButton {
                background-color: #007BFF;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:pressed {
                background-color: #004085;
            }
        """)
        top_layout.addWidget(self.print_both_btn)

        # 다중 선택 관련 버튼들
        self.select_all_btn = QPushButton("전체 선택")
        self.select_all_btn.clicked.connect(self.select_all_orders)
        top_layout.addWidget(self.select_all_btn)
        
        self.deselect_all_btn = QPushButton("선택 해제")
        self.deselect_all_btn.clicked.connect(self.deselect_all_orders)
        top_layout.addWidget(self.deselect_all_btn)
        
        self.batch_complete_btn = QPushButton("선택항목 완료")
        self.batch_complete_btn.clicked.connect(self.batch_mark_complete)
        self.batch_complete_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
        """)
        top_layout.addWidget(self.batch_complete_btn)
        
        self.batch_reset_btn = QPushButton("선택항목 초기화")
        self.batch_reset_btn.clicked.connect(self.batch_mark_new)
        self.batch_reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffc107;
                color: #212529;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e0a800;
            }
            QPushButton:pressed {
                background-color: #d39e00;
            }
        """)
        top_layout.addWidget(self.batch_reset_btn)
        
        # 주문취소 버튼 추가
        self.cancel_order_btn = QPushButton("주문취소")
        self.cancel_order_btn.clicked.connect(self.cancel_order)
        self.cancel_order_btn.setStyleSheet("""
            QPushButton {
                background-color: #DC143C;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #B22222;
            }
            QPushButton:pressed {
                background-color: #8B0000;
            }
        """)
        top_layout.addWidget(self.cancel_order_btn)
        
        layout.addLayout(top_layout)
        
        # 진행 상태 표시 바
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # 주문 테이블
        self.order_table = QTableWidget()
        self.order_table.setColumnCount(8)  # 체크박스 컬럼 추가
        self.order_table.setHorizontalHeaderLabels([
            "선택", "주문번호", "회사명", "메뉴", "매장식사", "총액", "상태", "주문일시"
        ])
        self.order_table.horizontalHeader().setStretchLastSection(True)
        self.order_table.setEditTriggers(QTableWidget.NoEditTriggers)  # 기본적으로 편집 비활성화
        self.order_table.setSelectionBehavior(QTableWidget.SelectRows)  # 행 전체 선택
        self.order_table.setSelectionMode(QTableWidget.MultiSelection)  # 다중 선택 허용
        
        # 체크박스 컬럼 크기 고정
        self.order_table.setColumnWidth(0, 50)
        layout.addWidget(self.order_table)

        # 알림 레이블
        self.notice_label = QLabel("")
        layout.addWidget(self.notice_label)
        
        # 스타일 설정
        self.setStyleSheet("""
            QTableWidget {
                background-color: white;
                border: 1px solid #ddd;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 4px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
            }
            QCheckBox {
                font-weight: bold;
                color: #2E7D32;
            }
            QComboBox {
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 3px;
                padding: 3px 5px;
                min-width: 80px;
            }
            QComboBox:hover {
                border: 1px solid #007BFF;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left-width: 1px;
                border-left-color: #ccc;
                border-left-style: solid;
            }
            QComboBox::down-arrow {
                image: none;
                border: 2px solid #666;
                width: 6px;
                height: 6px;
                border-top: none;
                border-right: none;
                transform: rotate(-45deg);
            }
        """)
    
    @Slot()
    def toggle_auto_print(self, state):
        """자동 출력 기능을 토글합니다."""
        # PySide6에서는 Qt.Checked.value와 비교해야 함
        enabled = state == Qt.Checked.value
        logging.info(f"자동 출력 체크박스 상태 변경: state={state}, enabled={enabled}")
        
        try:
            # 현재 설정 가져오기
            config = self.printer_manager.get_auto_print_config()
            logging.info(f"변경 전 설정: {config}")
            
            # 설정 업데이트
            old_enabled = config.get("enabled", False)
            config["enabled"] = enabled
            logging.info(f"설정 변경: {old_enabled} -> {enabled}")
            
            save_success = self.printer_manager.set_auto_print_config(config)
            logging.info(f"설정 저장 결과: {save_success}")
            
            # 모니터링 시스템의 자동출력 모드 조정
            if hasattr(self.order_monitor, 'set_auto_print_mode'):
                self.order_monitor.set_auto_print_mode(enabled)
            
            # 설정 저장 후 다시 확인
            updated_config = self.printer_manager.get_auto_print_config()
            logging.info(f"변경 후 설정: {updated_config}")
            
            # 파일에서도 직접 확인
            try:
                import json
                with open("printer_config.json", "r", encoding="utf-8") as f:
                    file_config = json.load(f)
                logging.info(f"파일에서 읽은 auto_print 설정: {file_config.get('auto_print', {})}")
            except Exception as file_e:
                logging.error(f"파일 읽기 오류: {file_e}")
            
            status = "활성화" if enabled else "비활성화"
            message = f"자동 출력이 {status}되었습니다."
            
            # 메시지 표시 및 로깅
            logging.info(f"메시지 표시: {message}")
            self.show_temporary_message(message, 3000)
            
        except Exception as e:
            logging.error(f"자동 출력 설정 변경 중 오류: {e}")
            logging.exception("전체 예외 스택:")
            self.show_temporary_message(f"자동 출력 설정 변경 중 오류가 발생했습니다: {str(e)}", 5000)
    

    
    def set_loading_state(self, is_loading):
        """로딩 상태에 따라 UI 요소들을 업데이트합니다."""
        self.refresh_btn.setEnabled(not is_loading)
        self.sync_btn.setEnabled(not is_loading)
        self.print_customer_btn.setEnabled(not is_loading)
        self.print_kitchen_btn.setEnabled(not is_loading)
        self.print_both_btn.setEnabled(not is_loading)
        self.cancel_order_btn.setEnabled(not is_loading)
        self.progress_bar.setVisible(is_loading)
        if is_loading:
            self.progress_bar.setRange(0, 0)  # 무한 로딩 표시
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(100)
    
    def update_order_status(self, order_id: int, is_printed: bool):
        """주문의 출력 상태를 업데이트합니다."""
        try:
            with sqlite3.connect(self.cache.db_path) as conn:
                cursor = conn.cursor()
                
                # 현재 시간
                now = datetime.now().isoformat()
                
                # is_printed 상태만 업데이트
                cursor.execute(
                    'UPDATE "order" SET is_printed = ?, last_print_attempt = ? WHERE order_id = ?',
                    (1 if is_printed else 0, now, order_id)
                )
                
                conn.commit()
                logging.info(f"주문 {order_id}의 출력 상태를 {is_printed}로 업데이트")
                
                # Supabase에도 상태 업데이트 시도
                if self.cache.base_url and is_printed:
                    try:
                        response = requests.patch(
                            f"{self.cache.base_url}/rest/v1/order",
                            headers=self.cache.headers,
                            json={"is_printed": True},
                            params={"order_id": f"eq.{order_id}"}
                        )
                        response.raise_for_status()
                    except Exception as e:
                        logging.error(f"Supabase 업데이트 실패: {e}")
                        
        except Exception as e:
            logging.error(f"주문 상태 업데이트 오류: {e}")

    def check_for_updates(self):
        """미출력 주문을 확인하고 자동 출력을 처리합니다."""
        try:
            # 자동 출력이 비활성화된 경우 처리하지 않음
            auto_print_enabled = self.printer_manager.is_auto_print_enabled()
            logging.debug(f"check_for_updates 호출됨 - 자동출력 활성화: {auto_print_enabled}")
            
            if not auto_print_enabled:
                logging.debug("자동 출력이 비활성화되어 있어 처리하지 않음")
                return
                
            # 주문 관련 테이블 동기화 (항상 수행)
            for table in ["order", "order_item", "order_item_option"]:
                self.cache.fetch_and_store_table(table)
            
            # 미출력 주문들 가져오기
            unprinteed_orders = self.get_unprinteed_orders()
            logging.info(f"미출력 주문 조회 결과: {len(unprinteed_orders)}개")
            
            if unprinteed_orders:
                logging.info(f"미출력 주문 {len(unprinteed_orders)}개를 확인했습니다.")
                for order in unprinteed_orders:
                    logging.info(f"미출력 주문 발견: ID={order.get('order_id')}, 회사={order.get('company_name')}")
                
                # 임시 메시지가 표시 중이 아닐 때만 미출력 주문 메시지 표시
                if not self.message_timer.isActive():
                    self.notice_label.setText(f"미출력 주문 {len(unprinteed_orders)}개 발견")
                
                # 각 미출력 주문에 대해 자동 출력 처리
                for order in unprinteed_orders:
                    order_detail = self.cache.join_order_detail(order["order_id"])
                    order_id = order_detail.get("order_id")
                    
                    logging.info(f"주문 {order_id} 자동 출력 시도")
                    
                    # 프린터 상태 확인
                    if not self.printer_manager.check_printer_status():
                        logging.warning(f"주문 {order_id}: 프린터 상태 불량으로 출력 건너뜀")
                        continue
                    
                    # 자동 출력 처리
                    success = self.process_auto_print(order_detail)
                    
                    if success:
                        logging.info(f"주문 {order_id} 자동 출력 성공")
                        # 출력 성공 시 is_printed 상태 업데이트
                        self.update_is_printed_status(order_id, True)
                    else:
                        logging.warning(f"주문 {order_id} 자동 출력 실패")
                
                # UI 새로고침
                self.refresh_orders()
            else:
                # 미출력 주문이 없으면 조용히 처리
                pass
                
        except Exception as e:
            logging.error(f"자동 출력 처리 오류: {e}")
            self.notice_label.setText("자동 출력 처리 중 오류가 발생했습니다.")
            # Supabase에도 에러 로깅
            error_logger = get_error_logger()
            if error_logger:
                error_logger.log_error(e, "자동 출력 처리 오류", {"context": "auto_print_processing"})

    def get_unprinteed_orders(self) -> List[Dict[str, Any]]:
        """출력되지 않은 주문들을 가져옵니다."""
        conn = sqlite3.connect(self.cache.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # is_printed가 0(False)인 주문들을 최신순으로 가져오기
        query = """
        SELECT o.order_id, o.company_id, o.is_dine_in, o.total_price, o.created_at,
               c.company_name
        FROM "order" o
        JOIN company c ON c.company_id = o.company_id
        WHERE o.is_printed = 0
        ORDER BY o.created_at DESC
        LIMIT 10
        """
        
        rows = cursor.execute(query).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def update_is_printed_status(self, order_id: int, is_printed: bool) -> None:
        """주문의 출력 상태를 업데이트합니다."""
        try:
            # 로컬 DB 업데이트
            with sqlite3.connect(self.cache.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'UPDATE "order" SET is_printed = ? WHERE order_id = ?',
                    (1 if is_printed else 0, order_id)
                )
                conn.commit()
                logging.info(f"주문 {order_id}의 출력 상태를 {is_printed}로 업데이트")
            
            # Supabase에도 업데이트 시도
            if self.cache.base_url:
                try:
                    response = requests.patch(
                        f"{self.cache.base_url}/rest/v1/order",
                        headers=self.cache.headers,
                        json={"is_printed": is_printed},
                        params={"order_id": f"eq.{order_id}"}
                    )
                    response.raise_for_status()
                    logging.info(f"Supabase에 주문 {order_id} 출력 상태 업데이트 성공")
                except Exception as e:
                    logging.error(f"Supabase 출력 상태 업데이트 실패: {e}")
                        
        except Exception as e:
            logging.error(f"출력 상태 업데이트 오류: {e}")

    def process_auto_print(self, order_data: dict) -> bool:
        """자동 출력을 처리합니다."""
        order_id = order_data.get("order_id")
        
        try:
            # 이미 출력된 주문인지 확인
            if order_data.get("is_printed", False):
                logging.info(f"주문 {order_id}: 이미 출력됨")
                return True
                
            # 주문 데이터 형식 변환
            formatted_order = {
                "order_id": str(order_data.get("order_id", "N/A")),
                "company_name": order_data.get("company_name", "N/A"),
                "created_at": order_data.get("created_at", ""),
                "is_dine_in": order_data.get("is_dine_in", True),
                "items": []
            }
            
            # 주문 항목 처리
            for item in order_data.get("items", []):
                formatted_item = {
                    "order_item_id": item.get("order_item_id"),
                    "name": item.get("name", "N/A"),
                    "quantity": item.get("quantity", 1),
                    "price": item.get("price", 0),
                    "options": item.get("options", [])
                }
                formatted_order["items"].append(formatted_item)
            
            # 양쪽 프린터 동시 출력 시도
            results = self.printer_manager.print_both_receipts(formatted_order)
            customer_success = results["customer"]
            kitchen_success = results["kitchen"]
            
            if customer_success and kitchen_success:
                # 모든 프린터 출력 성공
                self.update_order_status(order_id, True)
                logging.info(f"주문 {order_id} 자동 출력 성공 (손님용+주방용)")
                self.notice_label.setText(f"주문 {order_id}이(가) 자동으로 출력되었습니다 (손님용+주방용).")
                return True
            elif customer_success or kitchen_success:
                # 부분 성공
                success_printers = []
                if customer_success:
                    success_printers.append("손님용")
                if kitchen_success:
                    success_printers.append("주방용")
                
                logging.warning(f"주문 {order_id} 자동 출력 부분 성공: {', '.join(success_printers)}")
                self.notice_label.setText(f"주문 {order_id} 일부 프린터만 출력됨: {', '.join(success_printers)}")
                
                # 손님용 프린터만 성공해도 주문을 완료로 처리
                if customer_success:
                    self.update_order_status(order_id, True)
                    return True
                else:
                    self.update_order_status(order_id, False)
                    return False
            else:
                # 모든 프린터 출력 실패
                self.update_order_status(order_id, False)
                logging.error(f"주문 {order_id} 자동 출력 실패 (모든 프린터)")
                self.notice_label.setText(f"주문 {order_id} 자동 출력 실패")
                return False
                
        except Exception as e:
            logging.error(f"자동 출력 처리 오류: {e}")
            self.update_order_status(order_id, False)
            # Supabase에도 에러 로깅
            error_logger = get_error_logger()
            if error_logger:
                error_logger.log_printer_error(
                    printer_type="auto_print",
                    error=e,
                    order_id=str(order_id)
                )
            return False

    def should_retry_print(self, order_data: dict) -> bool:
        """재시도가 필요한지 확인합니다."""
        # 이미 출력된 주문은 재시도하지 않음
        if order_data.get("is_printed", False):
            return False
            
        last_attempt = order_data.get("last_print_attempt")
        if not last_attempt:
            return True
            
        try:
            last_attempt_time = datetime.fromisoformat(last_attempt)
            retry_interval = self.printer_manager.auto_print_config.get("retry_interval", 30)
            return datetime.now() >= last_attempt_time + timedelta(seconds=retry_interval)
        except Exception:
            return True
    
    @Slot()
    def refresh_orders(self):
        """주문 목록을 새로고침합니다."""
        try:
            self.set_loading_state(True)
            
            # 주문 관련 테이블 동기화
            for table in ["order", "order_item", "order_item_option"]:
                self.cache.fetch_and_store_table(table)

            orders = self.cache.get_recent_orders()

            # 테이블 초기화
            self.order_table.setRowCount(0)
            self.orders = []

            # 새로운 주문 데이터 추가 (최근 주문부터)
            for order in orders:
                detail = self.cache.join_order_detail(order["order_id"])
                self.add_order(detail)

            # 임시 메시지가 표시 중이 아닐 때만 갱신 메시지 표시
            if not self.message_timer.isActive():
                self.notice_label.setText("주문 목록이 갱신되었습니다.")

        except Exception as e:
            QMessageBox.warning(self, "오류", f"주문 목록 갱신 중 오류가 발생했습니다: {str(e)}")
            # Supabase에도 에러 로깅
            error_logger = get_error_logger()
            if error_logger:
                error_logger.log_error(e, "주문 목록 갱신 오류", {"context": "refresh_orders"})
        finally:
            self.set_loading_state(False)
    
    def get_selected_order_data(self):
        """선택된 주문 데이터를 가져와서 포맷팅합니다."""
        selected_items = self.order_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "경고", "출력할 주문을 선택해주세요.")
            return None
            
        # 선택된 주문 중 첫 번째 항목의 데이터를 사용
        selected_item = selected_items[0]
        order_data = selected_item.data(Qt.UserRole)
        
        if not order_data:
            QMessageBox.warning(self, "경고", "선택한 주문 데이터가 유효하지 않습니다.")
            return None
            
        # 주문 데이터 형식 변환
        formatted_order = {
            "order_id": str(order_data.get("order_id", "N/A")),
            "company_name": order_data.get("company_name", "N/A"),
            "created_at": order_data.get("created_at", ""),
            "is_dine_in": order_data.get("is_dine_in", True),
            "items": []
        }
        
        # 주문 항목 처리
        for item in order_data.get("items", []):
            formatted_item = {
                "order_item_id": item.get("order_item_id"),
                "name": item.get("name", "N/A"),
                "quantity": item.get("quantity", 1),
                "price": item.get("price", 0),
                "options": item.get("options", [])
            }
            formatted_order["items"].append(formatted_item)
        
        return formatted_order, order_data, self.order_table.row(selected_item)

    @Slot()
    def print_customer_receipt(self):
        """손님용 영수증만 출력합니다."""
        try:
            result = self.get_selected_order_data()
            if not result:
                return
            
            formatted_order, order_data, current_row = result
            
            # 디버깅을 위한 설정 정보 확인
            customer_config = self.printer_manager.get_customer_printer_config()
            logging.info(f"손님용 영수증 출력 시작 - 설정: {customer_config}")
            
            # 손님용 프린터 출력 시도
            success = self.printer_manager.print_customer_receipt(formatted_order)
            
            if success:
                QMessageBox.information(self, "성공", "손님용 영수증이 출력되었습니다.")
            else:
                QMessageBox.warning(self, "실패", f"손님용 영수증 출력에 실패했습니다.\n현재 설정: {customer_config.get('printer_type', 'Unknown')}")
                
        except Exception as e:
            QMessageBox.warning(self, "오류", f"손님용 영수증 출력 중 오류가 발생했습니다: {str(e)}")
            logging.error(f"손님용 영수증 출력 오류: {e}")

    @Slot()
    def print_kitchen_receipt(self):
        """주방용 영수증만 출력합니다."""
        try:
            result = self.get_selected_order_data()
            if not result:
                return
            
            formatted_order, order_data, current_row = result
            
            # 주방용 프린터 출력 시도
            success = self.printer_manager.print_kitchen_receipt(formatted_order)
            
            if success:
                QMessageBox.information(self, "성공", "주방용 영수증이 출력되었습니다.")
            else:
                QMessageBox.warning(self, "실패", "주방용 영수증 출력에 실패했습니다.\nCOM 포트 연결을 확인해주세요.")
                
        except Exception as e:
            QMessageBox.warning(self, "오류", f"주방용 영수증 출력 중 오류가 발생했습니다: {str(e)}")
            logging.error(f"주방용 영수증 출력 오류: {e}")

    @Slot()
    def print_both_receipts(self):
        """손님용과 주방용 영수증을 동시에 출력합니다."""
        try:
            result = self.get_selected_order_data()
            if not result:
                return
            
            formatted_order, order_data, current_row = result
            
            # 양쪽 프린터 동시 출력 시도
            results = self.printer_manager.print_both_receipts(formatted_order)
            
            customer_success = results["customer"]
            kitchen_success = results["kitchen"]
            
            if customer_success and kitchen_success:
                # 출력 성공 확인
                reply = QMessageBox.question(
                    self,
                    "출력 확인",
                    "손님용과 주방용 영수증이 모두 정상적으로 출력되었습니까?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )
                
                if reply == QMessageBox.Yes:
                    # 상태 업데이트
                    self.update_order_status(order_data["order_id"], True)
                    self.update_is_printed_status(order_data["order_id"], True)
                    
                    # UI 업데이트 - 드롭다운 위젯의 상태 변경
                    status_combo = self.order_table.cellWidget(current_row, 5)
                    if status_combo:
                        status_combo.setCurrentText("출력완료")
                    
                    QMessageBox.information(self, "성공", "영수증이 성공적으로 출력되었습니다.")
                else:
                    QMessageBox.warning(self, "출력 실패", "프린터 출력을 확인해주세요.")
            elif customer_success or kitchen_success:
                success_msg = []
                fail_msg = []
                if customer_success:
                    success_msg.append("손님용")
                else:
                    fail_msg.append("손님용")
                if kitchen_success:
                    success_msg.append("주방용")
                else:
                    fail_msg.append("주방용")
                
                message = f"출력 결과:\n성공: {', '.join(success_msg)}\n실패: {', '.join(fail_msg)}"
                QMessageBox.warning(self, "부분 성공", message)
            else:
                QMessageBox.warning(self, "실패", "양쪽 영수증 출력에 모두 실패했습니다.")
                
        except Exception as e:
            QMessageBox.warning(self, "오류", f"영수증 출력 중 오류가 발생했습니다: {str(e)}")
            logging.error(f"영수증 출력 오류: {e}")

    @Slot()
    def print_receipt(self):
        """기존 호환성을 위한 메서드 (동시 출력으로 연결)"""
        self.print_both_receipts()

    def add_order(self, order_data):
        """새로운 주문을 테이블에 추가"""
        try:
            row_position = self.order_table.rowCount()
            self.order_table.insertRow(row_position)

            # 체크박스 추가
            check_box = QCheckBox()
            check_box.setChecked(order_data.get("is_printed", False)) # 초기 상태 설정
            check_box.stateChanged.connect(lambda state, r=row_position: self.on_checkbox_changed(r, state))
            self.order_table.setCellWidget(row_position, 0, check_box)

            # 주문 데이터 설정
            order_id = str(order_data.get("order_id", "N/A"))
            item_id = QTableWidgetItem(order_id)
            item_id.setData(Qt.UserRole, order_data)
            self.order_table.setItem(row_position, 1, item_id)
            
            # 회사명
            company_name = order_data.get("company_name", "N/A")
            self.order_table.setItem(row_position, 2, QTableWidgetItem(company_name))
            
            # 메뉴 항목 구성
            items = order_data.get("items", [])
            items_text = "\n".join([
                f"{item.get('name', 'N/A')} x{item.get('quantity', 1)}"
                for item in items
            ])
            self.order_table.setItem(row_position, 3, QTableWidgetItem(items_text))
            
            # 매장식사 여부
            is_dine_in = "매장식사" if order_data.get("is_dine_in", True) else "포장"
            self.order_table.setItem(row_position, 4, QTableWidgetItem(is_dine_in))
            
            # 총액
            total_price = f"{order_data.get('total_price', 0):,}원"
            self.order_table.setItem(row_position, 5, QTableWidgetItem(total_price))
            
            # 상태 (기존 is_printed 기반) - 드롭다운으로 변경
            status = "출력완료" if order_data.get("is_printed", False) else "신규"
            
            # QComboBox 생성
            status_combo = QComboBox()
            status_combo.addItems(["신규", "출력완료"])
            status_combo.setCurrentText(status)
            
            # 상태 변경 이벤트 연결
            status_combo.currentTextChanged.connect(
                lambda new_status, row=row_position: self.on_status_changed(row, new_status)
            )
            
            # 테이블에 QComboBox 위젯 설정
            self.order_table.setCellWidget(row_position, 6, status_combo)
            
            # 주문일시
            created_at = order_data.get("created_at", "")
            if created_at:
                # ISO 형식의 날짜를 한국 시간(KST)으로 변환하여 표시
                from datetime import datetime, timezone
                from zoneinfo import ZoneInfo
                try:
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    dt = dt.astimezone(ZoneInfo("Asia/Seoul"))
                    created_at = dt.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    pass
            self.order_table.setItem(row_position, 7, QTableWidgetItem(created_at))
            
            self.orders.append(order_data)
        except Exception as e:
            QMessageBox.warning(self, "오류", f"주문 추가 중 오류가 발생했습니다: {str(e)}")

    @Slot()
    def sync_static_tables(self):
        """고정 테이블을 수동 동기화합니다."""
        tables = [
            "company",
            "menu_category",
            "menu_item",
            "menu_item_option_group",
            "option_group",
            "option_group_item",
            "option_item",
        ]
        try:
            self.set_loading_state(True)
            
            changes = []
            for table in tables:
                old_data = self.cache.get_table_data(table)
                self.cache.fetch_and_store_table(table)
                new_data = self.cache.get_table_data(table)
                
                # 변경사항 확인
                if old_data != new_data:
                    changes.append(f"{table}: {len(new_data) - len(old_data)}개 항목 변경")
            
            if changes:
                QMessageBox.information(
                    self, 
                    "동기화 완료", 
                    "고정 데이터 동기화가 완료되었습니다.\n\n변경사항:\n" + "\n".join(changes)
                )
            else:
                QMessageBox.information(self, "동기화 완료", "모든 데이터가 최신 상태입니다.")
                
        except Exception as e:
            QMessageBox.warning(self, "오류", f"동기화 중 오류가 발생했습니다: {str(e)}")
        finally:
            self.set_loading_state(False)

    def on_checkbox_changed(self, row, state):
        """체크박스 상태가 변경될 때 호출되는 메서드"""
        try:
            # 체크박스 상태를 확인하여 is_printed 값 결정
            is_printed = (state == Qt.Checked.value)
            
            # 주문 데이터 가져오기
            order_item = self.order_table.item(row, 0) # 체크박스 열
            if not order_item:
                return
                
            order_data = order_item.data(Qt.UserRole)
            if not order_data:
                return
                
            order_id = order_data.get("order_id")
            
            # 상태가 실제로 변경된 경우만 처리
            if order_data.get("is_printed") == is_printed:
                return
                
            logging.info(f"주문 {order_id} 출력 상태 변경: {order_data.get('is_printed')} -> {is_printed}")
            
            # 데이터베이스 업데이트
            self.update_order_status(order_id, is_printed)
            
            # 로컬 order_data도 업데이트
            order_data["is_printed"] = is_printed
            order_item.setData(Qt.UserRole, order_data)
            
            # 성공 메시지 표시
            self.show_temporary_message(f"주문 {order_id}의 출력 상태가 '{'출력완료' if is_printed else '신규'}'로 변경되었습니다.", 3000)
            
        except Exception as e:
            logging.error(f"체크박스 상태 변경 오류: {e}")
            QMessageBox.warning(self, "오류", f"출력 상태 변경 중 오류가 발생했습니다: {str(e)}")
            # 원래 상태로 되돌리기
            self.refresh_orders()

    def sync_auto_print_checkbox(self, show_message=False):
        """자동 출력 체크박스 상태를 실제 설정과 동기화합니다."""
        actual_state = self.printer_manager.is_auto_print_enabled()
        current_checkbox_state = self.auto_print_checkbox.isChecked()
        
        if actual_state != current_checkbox_state:
            logging.info(f"체크박스 상태 동기화: {current_checkbox_state} -> {actual_state}")
            # 시그널 연결을 일시적으로 해제하여 무한 루프 방지
            self.auto_print_checkbox.stateChanged.disconnect()
            self.auto_print_checkbox.setChecked(actual_state)
            self.auto_print_checkbox.stateChanged.connect(self.toggle_auto_print)
            
            # 메시지 표시 여부는 매개변수로 결정 (기본값: False)
            if show_message:
                status = "활성화" if actual_state else "비활성화"
                self.show_temporary_message(f"자동 출력이 {status}되었습니다.", 3000)
        
    def show_temporary_message(self, message: str, duration_ms: int = 2000):
        """임시 메시지를 지정된 시간 동안 표시합니다."""
        try:
            logging.debug(f"show_temporary_message 호출됨: '{message}', 지속시간: {duration_ms}ms")
            
            # 메시지 설정
            self.notice_label.setText(message)
            
            # 기존 타이머 중지 및 새 타이머 시작
            self.message_timer.stop()
            self.message_timer.start(duration_ms)
            
        except Exception as e:
            logging.error(f"show_temporary_message 오류: {e}")
            # 오류 발생 시 기본 메시지라도 표시하려고 시도
            try:
                self.notice_label.setText(message)
            except:
                pass
        
    def clear_temporary_message(self):
        """임시 메시지를 지웁니다."""
        self.notice_label.setText("")

    @Slot()
    def cancel_order(self):
        """선택된 주문을 취소(삭제)합니다."""
        try:
            # 체크박스로 선택된 주문들 가져오기
            selected_rows = self.get_selected_rows()
            
            if not selected_rows:
                QMessageBox.warning(self, "경고", "취소할 주문을 선택해주세요.")
                return
                
            # 선택된 주문들의 데이터를 가져오기
            orders_to_cancel = []
            for row in selected_rows:
                order_item = self.order_table.item(row, 1)  # 주문번호 컬럼
                if order_item:
                    order_data = order_item.data(Qt.UserRole)
                    if order_data:
                        orders_to_cancel.append((row, order_data))
            
            if not orders_to_cancel:
                QMessageBox.warning(self, "경고", "선택한 주문 데이터를 찾을 수 없습니다.")
                return
             
            # 확인 팝업 표시
            reply = QMessageBox.question(
                self,
                "주문 취소 확인",
                f"선택된 {len(orders_to_cancel)}개의 주문을 취소하시겠습니까?\n\n※ 주의: 취소된 주문은 복구할 수 없습니다.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply != QMessageBox.Yes:
                return
            
            # 로딩 상태 설정
            self.set_loading_state(True)
            
            # Supabase에서 주문 삭제
            from src.supabase_client import SupabaseClient
            supabase_client = SupabaseClient()
            
            successful_cancellations = []
            failed_cancellations = []
            
            for row, order_data in orders_to_cancel:
                order_id = order_data.get("order_id")
                try:
                    supabase_success = supabase_client.delete_order(order_id)
                    cache_success = self.cache.delete_order_from_cache(order_id)
                    
                    if supabase_success and cache_success:
                        successful_cancellations.append((row, order_id))
                    else:
                        failed_cancellations.append((row, order_id))
                        
                except Exception as e:
                    logging.error(f"주문 {order_id} 취소 중 오류: {e}")
                    failed_cancellations.append((row, order_id))
            
            # 성공한 주문들의 행을 역순으로 삭제 (인덱스 변경 방지)
            for row, order_id in sorted(successful_cancellations, reverse=True):
                self.order_table.removeRow(row)
                # orders 리스트에서도 제거
                self.orders = [order for order in self.orders if order.get("order_id") != order_id]
                logging.info(f"주문 {order_id} 취소 성공")
            
            # 결과 메시지 표시
            if successful_cancellations:
                success_msg = f"{len(successful_cancellations)}개 주문이 성공적으로 취소되었습니다."
                if failed_cancellations:
                    success_msg += f"\n{len(failed_cancellations)}개 주문 취소에 실패했습니다."
                    QMessageBox.warning(self, "부분 성공", success_msg)
                else:
                    QMessageBox.information(self, "성공", success_msg)
                    
                self.show_temporary_message(f"{len(successful_cancellations)}개 주문이 취소되었습니다.", 3000)
            else:
                QMessageBox.critical(self, "실패", "선택된 주문들의 취소에 모두 실패했습니다.")
                
        except Exception as e:
            QMessageBox.critical(self, "오류", f"주문 취소 중 오류가 발생했습니다:\n{str(e)}")
            logging.error(f"주문 취소 오류: {e}")
            # Supabase에도 에러 로깅
            error_logger = get_error_logger()
            if error_logger:
                error_logger.log_error(e, "주문 취소 오류", {"context": "cancel_order", "order_count": len(selected_rows) if 'selected_rows' in locals() else 0})
        finally:
            self.set_loading_state(False)

    def closeEvent(self, event):
        """위젯이 닫힐 때 모니터링 시스템 중지"""
        try:
            if self.order_monitor:
                self.order_monitor.stop_monitoring()
        except Exception as e:
            logging.error(f"모니터링 시스템 종료 오류: {e}")
        super().closeEvent(event)

    def on_status_changed(self, row, new_status):
        """상태 드롭다운이 변경될 때 호출되는 메서드"""
        try:
            # 주문 데이터 가져오기
            order_item = self.order_table.item(row, 0) # 체크박스 열
            if not order_item:
                return
                
            order_data = order_item.data(Qt.UserRole)
            if not order_data:
                return
                
            order_id = order_data.get("order_id")
            old_status = "출력완료" if order_data.get("is_printed", False) else "신규"
            
            # 상태가 실제로 변경된 경우만 처리
            if old_status == new_status:
                return
                
            logging.info(f"주문 {order_id} 상태 변경: {old_status} -> {new_status}")
            
            # 새로운 is_printed 값 결정
            is_printed = (new_status == "출력완료")
            
            # 데이터베이스 업데이트
            self.update_order_status(order_id, is_printed)
            
            # 로컬 order_data도 업데이트
            order_data["is_printed"] = is_printed
            order_item.setData(Qt.UserRole, order_data)
            
            # 성공 메시지 표시
            self.show_temporary_message(f"주문 {order_id}의 상태가 '{new_status}'로 변경되었습니다.", 3000)
            
        except Exception as e:
            logging.error(f"상태 변경 오류: {e}")
            QMessageBox.warning(self, "오류", f"상태 변경 중 오류가 발생했습니다: {str(e)}")
            # 원래 상태로 되돌리기
            self.refresh_orders()

    @Slot()
    def select_all_orders(self):
        """모든 주문을 선택합니다."""
        try:
            for row in range(self.order_table.rowCount()):
                checkbox = self.order_table.cellWidget(row, 0)
                if checkbox:
                    checkbox.setChecked(True)
            self.show_temporary_message(f"전체 {self.order_table.rowCount()}개 주문이 선택되었습니다.", 2000)
        except Exception as e:
            logging.error(f"전체 선택 오류: {e}")

    @Slot()
    def deselect_all_orders(self):
        """모든 주문 선택을 해제합니다."""
        try:
            for row in range(self.order_table.rowCount()):
                checkbox = self.order_table.cellWidget(row, 0)
                if checkbox:
                    checkbox.setChecked(False)
            self.show_temporary_message("모든 선택이 해제되었습니다.", 2000)
        except Exception as e:
            logging.error(f"선택 해제 오류: {e}")

    @Slot()
    def batch_mark_complete(self):
        """선택된 주문들을 일괄적으로 출력완료 상태로 변경합니다."""
        try:
            selected_rows = self.get_selected_rows()
            if not selected_rows:
                QMessageBox.warning(self, "경고", "변경할 주문을 선택해주세요.")
                return

            reply = QMessageBox.question(
                self,
                "일괄 상태 변경",
                f"선택된 {len(selected_rows)}개 주문을 '출력완료' 상태로 변경하시겠습니까?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )

            if reply == QMessageBox.Yes:
                success_count = 0
                for row in selected_rows:
                    order_item = self.order_table.item(row, 1)  # 주문번호 컬럼
                    if order_item:
                        order_data = order_item.data(Qt.UserRole)
                        if order_data:
                            order_id = order_data.get("order_id")
                            
                            # 데이터베이스 업데이트
                            self.update_order_status(order_id, True)
                            
                            # 로컬 데이터 업데이트
                            order_data["is_printed"] = True
                            order_item.setData(Qt.UserRole, order_data)
                            
                            # UI 업데이트
                            checkbox = self.order_table.cellWidget(row, 0)
                            if checkbox:
                                checkbox.setChecked(True)
                            
                            status_combo = self.order_table.cellWidget(row, 6)
                            if status_combo:
                                status_combo.setCurrentText("출력완료")
                            
                            success_count += 1

                self.show_temporary_message(f"{success_count}개 주문이 '출력완료' 상태로 변경되었습니다.", 3000)

        except Exception as e:
            logging.error(f"일괄 완료 처리 오류: {e}")
            QMessageBox.warning(self, "오류", f"일괄 상태 변경 중 오류가 발생했습니다: {str(e)}")

    @Slot()
    def batch_mark_new(self):
        """선택된 주문들을 일괄적으로 신규 상태로 변경합니다."""
        try:
            selected_rows = self.get_selected_rows()
            if not selected_rows:
                QMessageBox.warning(self, "경고", "변경할 주문을 선택해주세요.")
                return

            reply = QMessageBox.question(
                self,
                "일괄 상태 변경",
                f"선택된 {len(selected_rows)}개 주문을 '신규' 상태로 변경하시겠습니까?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )

            if reply == QMessageBox.Yes:
                success_count = 0
                for row in selected_rows:
                    order_item = self.order_table.item(row, 1)  # 주문번호 컬럼
                    if order_item:
                        order_data = order_item.data(Qt.UserRole)
                        if order_data:
                            order_id = order_data.get("order_id")
                            
                            # 데이터베이스 업데이트
                            self.update_order_status(order_id, False)
                            
                            # 로컬 데이터 업데이트
                            order_data["is_printed"] = False
                            order_item.setData(Qt.UserRole, order_data)
                            
                            # UI 업데이트
                            checkbox = self.order_table.cellWidget(row, 0)
                            if checkbox:
                                checkbox.setChecked(False)
                            
                            status_combo = self.order_table.cellWidget(row, 6)
                            if status_combo:
                                status_combo.setCurrentText("신규")
                            
                            success_count += 1

                self.show_temporary_message(f"{success_count}개 주문이 '신규' 상태로 변경되었습니다.", 3000)

        except Exception as e:
            logging.error(f"일괄 초기화 처리 오류: {e}")
            QMessageBox.warning(self, "오류", f"일괄 상태 변경 중 오류가 발생했습니다: {str(e)}")

    def get_selected_rows(self):
        """체크박스가 선택된 행들의 번호를 반환합니다."""
        selected_rows = []
        for row in range(self.order_table.rowCount()):
            checkbox = self.order_table.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
                selected_rows.append(row)
        return selected_rows
