from PySide6.QtCore import QObject, Signal
import logging

class WindowManager(QObject):
    """
    메인 윈도우와 컴팩트 위젯 간의 전환을 관리하는 클래스
    데이터 동기화와 상태 관리를 담당
    """
    
    def __init__(self, main_window, compact_widget):
        super().__init__()
        self.main_window = main_window
        self.compact_widget = compact_widget
        
        # 현재 모드 (True: 전체 GUI, False: 컴팩트 위젯)
        self.is_full_mode = True
        
        # 시그널 연결
        self.setup_connections()
        
        # 초기 설정
        self.compact_widget.hide()
        
        logging.info("WindowManager 초기화 완료")
        
    def setup_connections(self):
        """시그널 슬롯 연결 설정"""
        # 컴팩트 위젯에서 전체 GUI로 전환 요청
        self.compact_widget.expand_requested.connect(self.switch_to_full_mode)
        
    def switch_to_compact_mode(self):
        """컴팩트 위젯 모드로 전환"""
        if not self.is_full_mode:
            return
            
        logging.info("컴팩트 위젯 모드로 전환")
        
        try:
            # 메인 윈도우 숨기기
            self.main_window.hide()
            
            # 컴팩트 위젯 데이터 업데이트
            self._sync_data_to_compact()
            
            # 컴팩트 위젯 표시
            self.compact_widget.show()
            
            # 컴팩트 위젯을 화면 우상단에 위치시키기
            self._position_compact_widget()
            
            self.is_full_mode = False
            logging.info("컴팩트 위젯 모드 전환 완료")
            
        except Exception as e:
            logging.error(f"컴팩트 모드 전환 중 오류: {e}")
            # 오류 발생 시 전체 모드로 복귀
            self.switch_to_full_mode()
            
    def switch_to_full_mode(self):
        """전체 GUI 모드로 전환"""
        if self.is_full_mode:
            return
            
        logging.info("전체 GUI 모드로 전환")
        
        try:
            # 컴팩트 위젯 숨기기
            self.compact_widget.hide()
            
            # 메인 윈도우 데이터 동기화
            self._sync_data_to_main()
            
            # 메인 윈도우 표시
            self.main_window.show()
            self.main_window.raise_()  # 최상단으로 올리기
            self.main_window.activateWindow()  # 활성화
            
            self.is_full_mode = True
            logging.info("전체 GUI 모드 전환 완료")
            
        except Exception as e:
            logging.error(f"전체 모드 전환 중 오류: {e}")
            
    def _position_compact_widget(self):
        """컴팩트 위젯을 화면 우상단에 배치"""
        try:
            from PySide6.QtWidgets import QApplication
            screen = QApplication.primaryScreen()
            screen_geometry = screen.availableGeometry()
            
            # 우상단 위치 계산 (여백 20px)
            x = screen_geometry.width() - self.compact_widget.width() - 20
            y = 20
            
            self.compact_widget.move(x, y)
            logging.info(f"컴팩트 위젯 위치 설정: ({x}, {y})")
            
        except Exception as e:
            logging.error(f"컴팩트 위젯 위치 설정 오류: {e}")
            
    def _sync_data_to_compact(self):
        """메인 윈도우에서 컴팩트 위젯으로 데이터 동기화"""
        try:
            # 주문 위젯에서 데이터 가져오기
            order_widget = self.main_window.order_widget
            
            # 대기 중인 주문 수 계산 (is_printed 기준으로 통일)
            pending_orders = 0
            if hasattr(order_widget, 'orders') and order_widget.orders:
                pending_orders = len([order for order in order_widget.orders 
                                    if not order.get('is_printed', False)])
            
            # 자동출력 상태 확인
            auto_print_enabled = False
            if hasattr(order_widget, 'printer_manager'):
                auto_print_enabled = order_widget.printer_manager.is_auto_print_enabled()
            
            # 컴팩트 위젯에 데이터 전달
            data = {
                'pending_orders': pending_orders,
                'auto_print_enabled': auto_print_enabled,
                'last_update': order_widget.last_update_label.text() if hasattr(order_widget, 'last_update_label') else None
            }
            
            self.compact_widget.update_display(data)
            logging.info(f"컴팩트 위젯 데이터 동기화 완료: {data}")
            
        except Exception as e:
            logging.error(f"컴팩트 위젯 데이터 동기화 오류: {e}")
            
    def _sync_data_to_main(self):
        """컴팩트 위젯에서 메인 윈도우로 데이터 동기화"""
        try:
            # 메인 윈도우의 주문 데이터 새로고침
            if hasattr(self.main_window, 'order_widget'):
                self.main_window.order_widget.refresh_orders()
                logging.info("메인 윈도우 주문 데이터 새로고침 완료")
                
        except Exception as e:
            logging.error(f"메인 윈도우 데이터 동기화 오류: {e}")
            
    def get_compact_data(self):
        """컴팩트 위젯용 데이터 생성 콜백"""
        try:
            if not self.is_full_mode:
                # 컴팩트 모드일 때만 실시간 데이터 업데이트
                return self._get_current_order_data()
            return None
            
        except Exception as e:
            logging.error(f"컴팩트 데이터 생성 오류: {e}")
            return None
            
    def _get_current_order_data(self):
        """현재 주문 데이터를 가져오는 헬퍼 메소드"""
        try:
            # 데이터베이스나 캐시에서 직접 데이터 조회
            order_widget = self.main_window.order_widget
            
            pending_count = 0
            if hasattr(order_widget, 'cache'):
                try:
                    # 캐시에서 최신 주문 데이터 조회 (최근 50개)
                    orders = order_widget.cache.get_recent_orders(50)
                    # 아직 처리되지 않은 주문만 필터링 (출력되지 않거나 대기 상태)
                    pending_orders = [order for order in orders 
                                    if not order.get('is_printed', False)]
                    pending_count = len(pending_orders)
                except Exception as e:
                    logging.error(f"캐시에서 주문 데이터 조회 오류: {e}")
                    # 캐시 조회 실패 시 기존 방식 사용 (is_printed 기준으로 통일)
                    pending_count = len([order for order in getattr(order_widget, 'orders', []) 
                                       if not order.get('is_printed', False)])
            else:
                # 기존 orders 리스트 사용 (is_printed 기준으로 통일)
                pending_count = len([order for order in getattr(order_widget, 'orders', []) 
                                   if not order.get('is_printed', False)])
            
            auto_print_enabled = False
            if hasattr(order_widget, 'printer_manager'):
                auto_print_enabled = order_widget.printer_manager.is_auto_print_enabled()
                
            return {
                'pending_orders': pending_count,
                'auto_print_enabled': auto_print_enabled
            }
            
        except Exception as e:
            logging.error(f"현재 주문 데이터 조회 오류: {e}")
            return {'pending_orders': 0, 'auto_print_enabled': False}
            
    def toggle_mode(self):
        """현재 모드를 토글"""
        if self.is_full_mode:
            self.switch_to_compact_mode()
        else:
            self.switch_to_full_mode()
            
    def cleanup(self):
        """정리 작업"""
        try:
            if self.compact_widget:
                self.compact_widget.close()
            logging.info("WindowManager 정리 완료")
        except Exception as e:
            logging.error(f"WindowManager 정리 중 오류: {e}") 