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
    QScrollArea,
    QFrame,
    QGridLayout,
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
from src.gui.order_card import OrderCard

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
        
        layout.addLayout(top_layout)
        
        # 진행 상태 표시 바
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # 주문 카드 영역
        # 스크롤 영역 생성
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # 카드 컨테이너 위젯
        self.cards_widget = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_widget)
        self.cards_layout.setAlignment(Qt.AlignTop)
        self.cards_layout.setSpacing(10)
        self.cards_layout.setContentsMargins(10, 10, 10, 10)
        
        # 스크롤 영역에 컨테이너 설정
        self.scroll_area.setWidget(self.cards_widget)
        layout.addWidget(self.scroll_area)
        
        # 카드 목록 (주문 데이터 참조용)
        self.order_cards = []

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

    def update_approval_status(self, order_id: int, is_approved: bool) -> None:
        """주문의 승인 상태를 업데이트합니다."""
        try:
            # 로컬 DB 업데이트
            with sqlite3.connect(self.cache.db_path) as conn:
                cursor = conn.cursor()
                now = datetime.now().isoformat()
                
                if is_approved:
                    cursor.execute(
                        'UPDATE "order" SET is_approved = ?, approved_at = ?, approved_by = ? WHERE order_id = ?',
                        (1, now, "매장직원", order_id)
                    )
                else:
                    cursor.execute(
                        'UPDATE "order" SET is_approved = ?, approved_at = ?, approved_by = ? WHERE order_id = ?',
                        (0, None, None, order_id)
                    )
                
                conn.commit()
                logging.info(f"주문 {order_id}의 승인 상태를 {is_approved}로 업데이트")
            
            # Supabase에도 업데이트 시도
            if self.cache.base_url:
                try:
                    update_data = {"is_approved": is_approved}
                    if is_approved:
                        update_data["approved_at"] = now
                        update_data["approved_by"] = "매장직원"
                    else:
                        update_data["approved_at"] = None
                        update_data["approved_by"] = None
                    
                    response = requests.patch(
                        f"{self.cache.base_url}/rest/v1/order",
                        headers=self.cache.headers,
                        json=update_data,
                        params={"order_id": f"eq.{order_id}"}
                    )
                    response.raise_for_status()
                    logging.info(f"Supabase에 주문 {order_id} 승인 상태 업데이트 성공")
                except Exception as e:
                    logging.error(f"Supabase 승인 상태 업데이트 실패: {e}")
                        
        except Exception as e:
            logging.error(f"승인 상태 업데이트 오류: {e}")

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

            # 기존 카드들 모두 제거
            for card in self.order_cards:
                card.deleteLater()
            self.order_cards.clear()
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
    


    def add_order(self, order_data):
        """새로운 주문을 카드로 추가"""
        try:
            # 주문 카드 생성
            order_card = OrderCard(order_data, self)
            
            # 카드 시그널 연결
            order_card.order_approved.connect(self.on_order_approved)
            order_card.order_printed.connect(self.on_order_printed)
            
            # 카드를 레이아웃에 추가
            self.cards_layout.addWidget(order_card)
            
            # 카드 목록에 추가
            self.order_cards.append(order_card)
            self.orders.append(order_data)
            
        except Exception as e:
            QMessageBox.warning(self, "오류", f"주문 추가 중 오류가 발생했습니다: {str(e)}")
            logging.error(f"주문 카드 추가 오류: {e}")
    
    @Slot()
    def on_order_approved(self, order_id):
        """주문 승인 시그널을 처리합니다."""
        try:
            # 데이터베이스에 승인 상태 업데이트
            self.update_approval_status(order_id, True)
            
            # 카드 데이터 업데이트
            for card in self.order_cards:
                if card.order_id == order_id:
                    card.order_data["is_approved"] = True
                    card.order_data["approved_at"] = datetime.now().isoformat()
                    card.order_data["approved_by"] = "매장직원"
                    break
            
            self.show_temporary_message(f"주문 #{order_id}이(가) 승인되었습니다.", 3000)
            logging.info(f"주문 {order_id} 승인 완료")
            
        except Exception as e:
            logging.error(f"주문 승인 처리 오류: {e}")
            QMessageBox.warning(self, "오류", f"주문 승인 처리 중 오류가 발생했습니다: {str(e)}")
    
    @Slot()
    def on_order_printed(self, order_id):
        """주문 출력 시그널을 처리합니다."""
        try:
            # 해당 주문의 카드 찾기
            target_card = None
            for card in self.order_cards:
                if card.order_id == order_id:
                    target_card = card
                    break
            
            if not target_card:
                QMessageBox.warning(self, "오류", "출력할 주문을 찾을 수 없습니다.")
                return
            
            # 주문 데이터 형식 변환
            formatted_order = {
                "order_id": str(order_id),
                "company_name": target_card.order_data.get("company_name", "N/A"),
                "created_at": target_card.order_data.get("created_at", ""),
                "is_dine_in": target_card.order_data.get("is_dine_in", True),
                "items": []
            }
            
            # 주문 항목 처리
            for item in target_card.order_data.get("items", []):
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
                    self.update_order_status(order_id, True)
                    target_card.order_data["is_printed"] = True
                    target_card.update_order_data(target_card.order_data)
                    
                    self.show_temporary_message(f"주문 #{order_id} 영수증이 성공적으로 출력되었습니다.", 3000)
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
            logging.error(f"주문 출력 처리 오류: {e}")
            QMessageBox.warning(self, "오류", f"주문 출력 처리 중 오류가 발생했습니다: {str(e)}")

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

    def closeEvent(self, event):
        """위젯이 닫힐 때 모니터링 시스템 중지"""
        try:
            if self.order_monitor:
                self.order_monitor.stop_monitoring()
        except Exception as e:
            logging.error(f"모니터링 시스템 종료 오류: {e}")
        super().closeEvent(event)




