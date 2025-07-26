from PySide6.QtCore import QThread, Signal, QTimer, QMutex, QMutexLocker
from PySide6.QtWidgets import QApplication
import logging
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any
import requests

from src.database.cache import SupabaseCache
from src.printer.manager import PrinterManager
from src.error_logger import get_error_logger


class OrderMonitorThread(QThread):
    """주문 모니터링을 위한 백그라운드 스레드"""
    
    # 시그널 정의
    new_orders_found = Signal(list)  # 새로운 주문 발견
    auto_print_completed = Signal(int, bool)  # 자동출력 완료 (order_id, success)
    auto_print_failed = Signal(int, str)  # 자동출력 실패 (order_id, error_msg)
    connection_status_changed = Signal(bool)  # 연결 상태 변경
    
    def __init__(self, supabase_config, db_config):
        super().__init__()
        self.cache = SupabaseCache(db_path=db_config['path'], supabase_config=supabase_config)
        self.printer_manager = PrinterManager()
        
        # 스레드 제어
        self._running = False
        self._mutex = QMutex()
        
        # 설정 가능한 파라미터
        self.check_interval = 10  # 기본 10초 간격
        self.fast_check_interval = 3  # 빠른 체크 간격 (새 주문 감지 시)
        self.slow_check_interval = 30  # 느린 체크 간격 (활동 없을 때)
        self.last_order_time = None
        self.consecutive_empty_checks = 0
        
    def start_monitoring(self):
        """모니터링 시작"""
        self._running = True
        self.start()
        
    def stop_monitoring(self):
        """모니터링 중지"""
        self._running = False
        self.wait()  # 스레드 종료 대기
        
    def set_check_interval(self, interval: int):
        """체크 간격 설정"""
        with QMutexLocker(self._mutex):
            self.check_interval = max(3, interval)  # 최소 3초
            
    def run(self):
        """메인 모니터링 루프"""
        logging.info("주문 모니터링 스레드 시작")
        logging.info(f"자동출력 활성화 상태: {self.printer_manager.is_auto_print_enabled()}")
        
        while self._running:
            try:
                # 동적 간격 계산
                current_interval = self._calculate_dynamic_interval()
                logging.debug(f"모니터링 간격: {current_interval}초")
                
                # 주문 확인 및 처리
                self._check_and_process_orders()
                
                # 다음 체크까지 대기 (중간에 중지 신호 확인)
                for _ in range(current_interval):
                    if not self._running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                logging.error(f"주문 모니터링 중 오류: {e}")
                time.sleep(5)  # 오류 시 5초 대기
                
        logging.info("주문 모니터링 스레드 종료")
        
    def _calculate_dynamic_interval(self) -> int:
        """동적 체크 간격 계산"""
        # 자동출력이 활성화된 경우 더 자주 체크
        auto_print_enabled = self.printer_manager.is_auto_print_enabled()
        logging.debug(f"자동출력 활성화 상태 체크: {auto_print_enabled}")
        
        if auto_print_enabled:
            base_interval = self.fast_check_interval
        else:
            base_interval = self.check_interval
            
        # 연속으로 빈 체크가 많으면 간격 늘리기
        if self.consecutive_empty_checks > 10:
            return min(self.slow_check_interval, base_interval * 2)
        elif self.consecutive_empty_checks > 5:
            return base_interval + 5
        else:
            return base_interval
            
    def _check_and_process_orders(self):
        """주문 확인 및 처리"""
        try:
            logging.debug("주문 확인 및 처리 시작")
            
            # 1. 연결 상태 확인
            connection_ok = self._check_connection()
            logging.debug(f"연결 상태: {connection_ok}")
            self.connection_status_changed.emit(connection_ok)
            
            if not connection_ok:
                logging.warning("연결 상태 불량으로 처리 중단")
                return
                
            # 2. 주문 데이터 동기화 (경량화)
            logging.debug("필수 테이블 동기화 시작")
            self._sync_essential_tables()
            
            # 3. 새로운 주문 확인
            logging.debug("새로운 주문 조회 시작")
            new_orders = self._get_new_orders()
            logging.info(f"조회된 미출력 주문: {len(new_orders)}개")
            
            if new_orders:
                logging.info("새로운 주문이 발견되었습니다:")
                for order in new_orders:
                    logging.info(f"  주문ID: {order.get('order_id')}, 회사: {order.get('company_name')}, 출력상태: {order.get('is_printed')}")
                
                self.consecutive_empty_checks = 0
                self.last_order_time = datetime.now()
                self.new_orders_found.emit(new_orders)
                
                # 4. 자동출력 처리 (별도 처리)
                auto_print_enabled = self.printer_manager.is_auto_print_enabled()
                logging.info(f"자동출력 활성화 상태: {auto_print_enabled}")
                
                if auto_print_enabled:
                    logging.info(f"{len(new_orders)}개 주문에 대해 자동출력 처리 시작")
                    self._process_auto_print_orders(new_orders)
                else:
                    logging.info("자동출력이 비활성화되어 있어 처리하지 않음")
            else:
                self.consecutive_empty_checks += 1
                logging.debug(f"미출력 주문 없음 (연속 빈 체크: {self.consecutive_empty_checks}회)")
                
        except Exception as e:
            logging.error(f"주문 처리 중 오류: {e}")
            import traceback
            logging.error(f"상세 오류: {traceback.format_exc()}")
            
    def _check_connection(self) -> bool:
        """네트워크 연결 상태 확인"""
        try:
            if not self.cache.base_url:
                return False
                
            response = requests.get(
                f"{self.cache.base_url}/rest/v1/company",
                headers=self.cache.headers,
                timeout=5,
                params={"select": "company_id", "limit": "1"}
            )
            return response.status_code == 200
        except:
            return False
            
    def _sync_essential_tables(self):
        """필수 테이블만 동기화 (성능 최적화)"""
        essential_tables = ["order", "order_item", "order_item_option", "company", "menu_item", "option_item"]
        for table in essential_tables:
            try:
                self.cache.fetch_and_store_table(table)
            except Exception as e:
                logging.warning(f"테이블 {table} 동기화 실패: {e}")
                
    def _get_new_orders(self) -> List[Dict[str, Any]]:
        """새로운 주문 조회 (최적화된 쿼리)"""
        import sqlite3
        
        conn = sqlite3.connect(self.cache.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 최근 1시간 내의 미출력 주문만 조회
        query = """
        SELECT o.order_id, o.company_id, o.is_dine_in, o.total_price, 
               o.created_at, o.is_printed, c.company_name
        FROM "order" o
        JOIN company c ON c.company_id = o.company_id
        WHERE o.is_printed = 0 
        AND datetime(o.created_at) > datetime('now', '-1 hour')
        ORDER BY o.created_at DESC
        LIMIT 20
        """
        
        rows = cursor.execute(query).fetchall()
        conn.close()
        return [dict(row) for row in rows]
        
    def _process_auto_print_orders(self, orders: List[Dict[str, Any]]):
        """자동출력 처리 (비동기)"""
        logging.info(f"자동출력 처리 시작: {len(orders)}개 주문")
        
        for order in orders:
            if not self._running:
                logging.info("모니터링 중지로 자동출력 처리 중단")
                break
                
            try:
                order_id = order.get("order_id")
                logging.info(f"주문 {order_id} 자동출력 처리 시작")
                
                # 프린터 상태 확인
                printer_status_ok = self.printer_manager.check_printer_status()
                logging.info(f"주문 {order_id}: 프린터 상태 = {printer_status_ok}")
                
                if not printer_status_ok:
                    logging.warning(f"주문 {order_id}: 프린터 상태 불량으로 건너뜀")
                    continue
                
                # 주문 상세 정보 가져오기
                logging.debug(f"주문 {order_id}: 상세 정보 조회 중")
                order_detail = self.cache.join_order_detail(order_id)
                
                if not order_detail:
                    logging.warning(f"주문 {order_id}: 상세 정보 조회 실패")
                    continue
                
                logging.info(f"주문 {order_id}: 상세 정보 조회 성공, 아이템 {len(order_detail.get('items', []))}개")
                    
                # 자동출력 실행
                logging.info(f"주문 {order_id}: 자동출력 실행 시작")
                success = self._execute_auto_print(order_detail)
                
                if success:
                    logging.info(f"주문 {order_id}: 자동출력 성공")
                    self.auto_print_completed.emit(order_id, True)
                    # 출력 상태 업데이트
                    self._update_print_status(order_id, True)
                else:
                    logging.error(f"주문 {order_id}: 자동출력 실패")
                    self.auto_print_failed.emit(order_id, "출력 실패")
                    
            except Exception as e:
                order_id = order.get('order_id', 'Unknown')
                logging.error(f"주문 {order_id} 자동출력 중 예외 발생: {e}")
                import traceback
                logging.error(f"상세 오류: {traceback.format_exc()}")
                self.auto_print_failed.emit(order_id, str(e))
                
    def _execute_auto_print(self, order_data: dict) -> bool:
        """실제 프린터 출력 실행"""
        try:
            order_id = order_data.get("order_id", "N/A")
            logging.info(f"주문 {order_id}: 프린터 출력 실행 시작")
            
            # 주문 데이터 포맷팅
            formatted_order = {
                "order_id": str(order_data.get("order_id", "N/A")),
                "company_name": order_data.get("company_name", "N/A"),
                "created_at": order_data.get("created_at", ""),
                "is_dine_in": order_data.get("is_dine_in", True),
                "total_price": order_data.get("total_price", 0),  # 데이터베이스의 total_price 포함
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
                
                # 옵션 정보 로깅 추가
                options = item.get("options", [])
                if options:
                    logging.info(f"주문 {order_id}: 아이템 '{item.get('name')}' 옵션 {len(options)}개 포함")
                    for opt in options:
                        logging.debug(f"  옵션: {opt.get('name')} x{opt.get('quantity', 1)} = {opt.get('total_price', 0)}원")
                else:
                    logging.debug(f"주문 {order_id}: 아이템 '{item.get('name')}' 옵션 없음")
            
            logging.info(f"주문 {order_id}: 포맷팅 완료, 아이템 {len(formatted_order['items'])}개")
            
            # 양쪽 프린터 출력
            logging.info(f"주문 {order_id}: 프린터 출력 시작")
            results = self.printer_manager.print_both_receipts(formatted_order)
            
            customer_success = results.get("customer", False)
            kitchen_success = results.get("kitchen", False)
            
            logging.info(f"주문 {order_id}: 출력 결과 - 손님용: {customer_success}, 주방용: {kitchen_success}")
            
            # 적어도 하나가 성공하면 성공으로 간주
            overall_success = customer_success or kitchen_success
            
            if overall_success:
                logging.info(f"주문 {order_id}: 자동출력 완료")
            else:
                logging.error(f"주문 {order_id}: 모든 프린터 출력 실패")
            
            return overall_success
            
        except Exception as e:
            order_id = order_data.get("order_id", "N/A")
            logging.error(f"주문 {order_id}: 프린터 출력 중 예외 발생: {e}")
            import traceback
            logging.error(f"상세 오류: {traceback.format_exc()}")
            return False
            
    def _update_print_status(self, order_id: int, is_printed: bool):
        """출력 상태 업데이트"""
        try:
            import sqlite3
            
            # 로컬 DB 업데이트
            with sqlite3.connect(self.cache.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'UPDATE "order" SET is_printed = ? WHERE order_id = ?',
                    (1 if is_printed else 0, order_id)
                )
                conn.commit()
            
            # Supabase 업데이트 (비동기)
            if self.cache.base_url:
                try:
                    requests.patch(
                        f"{self.cache.base_url}/rest/v1/order",
                        headers=self.cache.headers,
                        json={"is_printed": is_printed},
                        params={"order_id": f"eq.{order_id}"},
                        timeout=10
                    )
                except Exception as e:
                    logging.error(f"Supabase 업데이트 실패: {e}")
                    
        except Exception as e:
            logging.error(f"출력 상태 업데이트 오류: {e}")


class SmartOrderMonitor:
    """스마트 주문 모니터링 매니저"""
    
    def __init__(self, order_widget, supabase_config, db_config):
        self.order_widget = order_widget
        self.monitor_thread = OrderMonitorThread(supabase_config, db_config)
        self.is_monitoring = False
        
        # 시그널 연결
        self.monitor_thread.new_orders_found.connect(self._on_new_orders)
        self.monitor_thread.auto_print_completed.connect(self._on_auto_print_completed)
        self.monitor_thread.auto_print_failed.connect(self._on_auto_print_failed)
        self.monitor_thread.connection_status_changed.connect(self._on_connection_changed)
        
    def start_monitoring(self):
        """모니터링 시작"""
        if not self.is_monitoring:
            self.monitor_thread.start_monitoring()
            self.is_monitoring = True
            logging.info("스마트 주문 모니터링 시작")
            
    def stop_monitoring(self):
        """모니터링 중지"""
        if self.is_monitoring:
            self.monitor_thread.stop_monitoring()
            self.is_monitoring = False
            logging.info("스마트 주문 모니터링 중지")
            
    def set_auto_print_mode(self, enabled: bool):
        """자동출력 모드 설정"""
        if enabled:
            self.monitor_thread.set_check_interval(3)  # 빠른 체크
        else:
            self.monitor_thread.set_check_interval(15)  # 느린 체크
            
    def _on_new_orders(self, orders):
        """새 주문 발견 시 호출"""
        QApplication.processEvents()  # GUI 업데이트 허용
        self.order_widget.refresh_orders()
        
        if orders:
            count = len(orders)
            self.order_widget.show_temporary_message(
                f"새로운 주문 {count}개가 접수되었습니다.", 3000
            )
            
    def _on_auto_print_completed(self, order_id, success):
        """자동출력 완료 시 호출"""
        QApplication.processEvents()
        self.order_widget.show_temporary_message(
            f"주문 {order_id}이(가) 자동으로 출력되었습니다.", 3000
        )
        
    def _on_auto_print_failed(self, order_id, error_msg):
        """자동출력 실패 시 호출"""
        QApplication.processEvents()
        self.order_widget.show_temporary_message(
            f"주문 {order_id} 자동출력 실패: {error_msg}", 5000
        )
        
    def _on_connection_changed(self, is_connected):
        """연결 상태 변경 시 호출"""
        if hasattr(self.order_widget, 'connection_indicator'):
            # 연결 상태 표시 업데이트 (UI가 있다면)
            pass 