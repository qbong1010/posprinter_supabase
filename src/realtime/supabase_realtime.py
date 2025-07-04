import json
import logging
import websocket
import threading
import time
from typing import Callable, Dict, Any, Optional
from PySide6.QtCore import QObject, Signal


class SupabaseRealtimeClient(QObject):
    """Supabase 실시간 데이터 구독 클라이언트"""
    
    # Qt 시그널 정의
    order_inserted = Signal(dict)  # 새 주문 추가
    order_updated = Signal(dict)   # 주문 업데이트
    connection_status_changed = Signal(bool)  # 연결 상태 변경
    
    def __init__(self, supabase_url: str, api_key: str):
        super().__init__()
        
        # Supabase 실시간 WebSocket URL 구성
        # wss://your-project.supabase.co/realtime/v1/websocket
        self.ws_url = supabase_url.replace('https://', 'wss://').replace('http://', 'ws://') + '/realtime/v1/websocket'
        self.api_key = api_key
        
        self.ws = None
        self.is_connected = False
        self.should_reconnect = True
        self.reconnect_interval = 5.0
        self.last_ping = 0
        
        # 구독 관리
        self.subscriptions = {}
        self.ref_counter = 1
        
        logging.info(f"Supabase 실시간 클라이언트 초기화: {self.ws_url}")
        
    def connect(self):
        """WebSocket 연결 시작"""
        try:
            # WebSocket 연결 설정
            websocket.enableTrace(False)  # 디버깅용
            
            self.ws = websocket.WebSocketApp(
                self.ws_url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close
            )
            
            # 별도 스레드에서 WebSocket 실행
            self.ws_thread = threading.Thread(
                target=self.ws.run_forever,
                daemon=True
            )
            self.ws_thread.start()
            
            logging.info("Supabase 실시간 연결 시도 중...")
            
        except Exception as e:
            logging.error(f"WebSocket 연결 오류: {e}")
            
    def disconnect(self):
        """WebSocket 연결 종료"""
        self.should_reconnect = False
        if self.ws:
            self.ws.close()
            
    def subscribe_to_orders(self):
        """주문 테이블 실시간 구독"""
        if not self.is_connected:
            logging.warning("WebSocket이 연결되지 않았습니다.")
            return
            
        subscription_payload = {
            "topic": "realtime:public:order",
            "event": "phx_join",
            "payload": {
                "config": {
                    "postgres_changes": [
                        {
                            "event": "INSERT",
                            "schema": "public",
                            "table": "order"
                        },
                        {
                            "event": "UPDATE", 
                            "schema": "public",
                            "table": "order"
                        }
                    ]
                }
            },
            "ref": str(self.ref_counter)
        }
        
        self.subscriptions["order"] = self.ref_counter
        self.ref_counter += 1
        
        try:
            self.ws.send(json.dumps(subscription_payload))
            logging.info("주문 테이블 실시간 구독 요청 전송")
        except Exception as e:
            logging.error(f"구독 요청 오류: {e}")
            
    def _on_open(self, ws):
        """WebSocket 연결 성공"""
        logging.info("Supabase 실시간 연결 성공")
        self.is_connected = True
        self.connection_status_changed.emit(True)
        
        # 연결 후 즉시 주문 구독
        self.subscribe_to_orders()
        
        # Heartbeat 시작
        self._start_heartbeat()
        
    def _on_message(self, ws, message):
        """WebSocket 메시지 수신"""
        try:
            data = json.loads(message)
            event = data.get("event")
            payload = data.get("payload", {})
            
            if event == "postgres_changes":
                self._handle_postgres_change(payload)
            elif event == "phx_reply":
                self._handle_subscription_reply(data)
            elif event == "heartbeat":
                self.last_ping = time.time()
                
        except Exception as e:
            logging.error(f"메시지 처리 오류: {e}")
            logging.debug(f"받은 메시지: {message}")
            
    def _handle_postgres_change(self, payload):
        """PostgreSQL 변경 이벤트 처리"""
        try:
            schema = payload.get("schema")
            table = payload.get("table")
            event_type = payload.get("eventType")
            
            if schema == "public" and table == "order":
                if event_type == "INSERT":
                    new_record = payload.get("new", {})
                    logging.info(f"새 주문 감지: {new_record.get('order_id')}")
                    self.order_inserted.emit(new_record)
                    
                elif event_type == "UPDATE":
                    new_record = payload.get("new", {})
                    old_record = payload.get("old", {})
                    logging.info(f"주문 업데이트: {new_record.get('order_id')}")
                    self.order_updated.emit({
                        "new": new_record,
                        "old": old_record
                    })
                    
        except Exception as e:
            logging.error(f"PostgreSQL 변경 처리 오류: {e}")
            
    def _handle_subscription_reply(self, data):
        """구독 응답 처리"""
        status = data.get("payload", {}).get("status")
        if status == "ok":
            logging.info("주문 테이블 실시간 구독 성공")
        else:
            logging.error(f"구독 실패: {data}")
            
    def _on_error(self, ws, error):
        """WebSocket 오류"""
        logging.error(f"WebSocket 오류: {error}")
        self.is_connected = False
        self.connection_status_changed.emit(False)
        
    def _on_close(self, ws, close_status_code, close_msg):
        """WebSocket 연결 종료"""
        logging.info(f"WebSocket 연결 종료: {close_status_code} {close_msg}")
        self.is_connected = False
        self.connection_status_changed.emit(False)
        
        # 자동 재연결
        if self.should_reconnect:
            logging.info(f"{self.reconnect_interval}초 후 재연결 시도...")
            time.sleep(self.reconnect_interval)
            self.connect()
            
    def _start_heartbeat(self):
        """Heartbeat 전송 시작"""
        def send_heartbeat():
            while self.is_connected and self.should_reconnect:
                try:
                    if self.ws:
                        heartbeat_payload = {
                            "topic": "phoenix",
                            "event": "heartbeat",
                            "payload": {},
                            "ref": str(self.ref_counter)
                        }
                        self.ref_counter += 1
                        self.ws.send(json.dumps(heartbeat_payload))
                        
                    time.sleep(30)  # 30초마다 heartbeat
                except Exception as e:
                    logging.error(f"Heartbeat 오류: {e}")
                    break
                    
        heartbeat_thread = threading.Thread(target=send_heartbeat, daemon=True)
        heartbeat_thread.start()


class RealtimeOrderMonitor:
    """실시간 주문 모니터링 통합 클래스"""
    
    def __init__(self, order_widget, supabase_config):
        self.order_widget = order_widget
        self.realtime_client = SupabaseRealtimeClient(
            supabase_config['url'], 
            supabase_config['api_key']
        )
        
        # 시그널 연결
        self.realtime_client.order_inserted.connect(self._on_new_order)
        self.realtime_client.order_updated.connect(self._on_order_updated)
        self.realtime_client.connection_status_changed.connect(self._on_connection_changed)
        
        self.is_monitoring = False
        
    def start_monitoring(self):
        """실시간 모니터링 시작"""
        if not self.is_monitoring:
            self.realtime_client.connect()
            self.is_monitoring = True
            logging.info("실시간 주문 모니터링 시작")
            
    def stop_monitoring(self):
        """실시간 모니터링 중지"""
        if self.is_monitoring:
            self.realtime_client.disconnect()
            self.is_monitoring = False
            logging.info("실시간 주문 모니터링 중지")
            
    def _on_new_order(self, order_data):
        """새 주문 수신 시 처리"""
        try:
            order_id = order_data.get('order_id')
            logging.info(f"실시간 새 주문 수신: {order_id}")
            
            # UI 새로고침 (메인 스레드에서 실행)
            self.order_widget.refresh_orders()
            
            # 자동출력 처리
            if self.order_widget.printer_manager.is_auto_print_enabled():
                self._process_realtime_auto_print(order_id)
                
            # 알림 메시지
            self.order_widget.show_temporary_message(
                f"새로운 주문 {order_id}번이 접수되었습니다.", 3000
            )
            
        except Exception as e:
            logging.error(f"새 주문 처리 오류: {e}")
            
    def _on_order_updated(self, update_data):
        """주문 업데이트 수신 시 처리"""
        try:
            new_data = update_data.get('new', {})
            old_data = update_data.get('old', {})
            order_id = new_data.get('order_id')
            
            logging.info(f"실시간 주문 업데이트: {order_id}")
            
            # UI 새로고침
            self.order_widget.refresh_orders()
            
        except Exception as e:
            logging.error(f"주문 업데이트 처리 오류: {e}")
            
    def _on_connection_changed(self, is_connected):
        """연결 상태 변경 시 처리"""
        status = "연결됨" if is_connected else "연결 끊김"
        logging.info(f"실시간 연결 상태: {status}")
        
        # UI에 연결 상태 표시
        if hasattr(self.order_widget, 'realtime_status_label'):
            self.order_widget.realtime_status_label.setText(
                f"실시간: {status}"
            )
            
    def _process_realtime_auto_print(self, order_id):
        """실시간 자동출력 처리"""
        try:
            # 별도 스레드에서 프린터 작업 실행
            def print_worker():
                try:
                    # 주문 상세 정보 조회
                    order_detail = self.order_widget.cache.join_order_detail(order_id)
                    if not order_detail:
                        return
                        
                    # 프린터 상태 확인
                    if not self.order_widget.printer_manager.check_printer_status():
                        logging.warning(f"주문 {order_id}: 프린터 상태 불량")
                        return
                        
                    # 자동출력 실행
                    success = self._execute_auto_print(order_detail)
                    
                    if success:
                        # 출력 상태 업데이트
                        self.order_widget.update_is_printed_status(order_id, True)
                        
                        # 성공 메시지 (메인 스레드에서 실행)
                        self.order_widget.show_temporary_message(
                            f"주문 {order_id}이(가) 자동으로 출력되었습니다.", 3000
                        )
                    else:
                        # 실패 메시지
                        self.order_widget.show_temporary_message(
                            f"주문 {order_id} 자동출력에 실패했습니다.", 5000
                        )
                        
                except Exception as e:
                    logging.error(f"실시간 자동출력 오류: {e}")
                    
            # 백그라운드에서 실행
            threading.Thread(target=print_worker, daemon=True).start()
            
        except Exception as e:
            logging.error(f"실시간 자동출력 처리 오류: {e}")
            
    def _execute_auto_print(self, order_data: dict) -> bool:
        """프린터 출력 실행 (SmartOrderMonitor와 동일한 로직)"""
        try:
            # 주문 데이터 포맷팅
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
                    "name": item.get("name", "N/A"),
                    "quantity": item.get("quantity", 1),
                    "price": item.get("price", 0),
                    "options": item.get("options", [])
                }
                formatted_order["items"].append(formatted_item)
            
            # 양쪽 프린터 출력
            results = self.order_widget.printer_manager.print_both_receipts(formatted_order)
            
            # 손님용 프린터만 성공해도 완료로 처리
            return results.get("customer", False)
            
        except Exception as e:
            logging.error(f"프린터 출력 실행 중 오류: {e}")
            return False 