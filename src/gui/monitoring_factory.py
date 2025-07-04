import json
import logging
from pathlib import Path
from typing import Optional, Union

from src.gui.order_monitor import SmartOrderMonitor
from src.realtime.supabase_realtime import RealtimeOrderMonitor


class MonitoringFactory:
    """모니터링 시스템 팩토리"""
    
    def __init__(self, order_widget, supabase_config, db_config):
        self.order_widget = order_widget
        self.supabase_config = supabase_config
        self.db_config = db_config
        self.current_monitor = None
        
        # 설정 로드
        self.config = self._load_config()
        
    def _load_config(self) -> dict:
        """모니터링 설정 로드"""
        config_file = Path("monitor_config.json")
        
        if not config_file.exists():
            # 기본 설정 반환
            return {
                "monitoring": {
                    "method": "smart_polling",
                    "realtime_enabled": False
                }
            }
            
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"모니터링 설정 로드 오류: {e}")
            return {"monitoring": {"method": "smart_polling"}}
            
    def create_monitor(self) -> Optional[Union[SmartOrderMonitor, RealtimeOrderMonitor]]:
        """설정에 따라 적절한 모니터 생성"""
        method = self.config.get("monitoring", {}).get("method", "smart_polling")
        
        try:
            if method == "realtime":
                logging.info("실시간 WebSocket 모니터링 생성")
                return RealtimeOrderMonitor(self.order_widget, self.supabase_config)
                
            elif method == "smart_polling":
                logging.info("스마트 폴링 모니터링 생성")
                return SmartOrderMonitor(self.order_widget, self.supabase_config, self.db_config)
                
            elif method == "hybrid":
                logging.info("하이브리드 모니터링 생성")
                return self._create_hybrid_monitor()
                
            else:
                logging.warning(f"알 수 없는 모니터링 방식: {method}, 기본값 사용")
                return SmartOrderMonitor(self.order_widget, self.supabase_config, self.db_config)
                
        except Exception as e:
            logging.error(f"모니터 생성 오류: {e}")
            # 폴백으로 스마트 폴링 사용
            return SmartOrderMonitor(self.order_widget, self.supabase_config, self.db_config)
            
    def _create_hybrid_monitor(self):
        """하이브리드 모니터링 생성 (실시간 + 폴링)"""
        class HybridMonitor:
            def __init__(self, order_widget, supabase_config, db_config):
                # 실시간 모니터 (주)
                self.realtime_monitor = RealtimeOrderMonitor(order_widget, supabase_config)
                # 폴링 모니터 (보조)
                self.polling_monitor = SmartOrderMonitor(order_widget, supabase_config, db_config)
                self.polling_monitor.monitor_thread.set_check_interval(60)  # 느린 폴링
                
            def start_monitoring(self):
                self.realtime_monitor.start_monitoring()
                self.polling_monitor.start_monitoring()
                
            def stop_monitoring(self):
                self.realtime_monitor.stop_monitoring()
                self.polling_monitor.stop_monitoring()
                
            def set_auto_print_mode(self, enabled: bool):
                # 실시간 모니터는 자동 조정되므로 폴링만 조정
                if enabled:
                    self.polling_monitor.monitor_thread.set_check_interval(30)
                else:
                    self.polling_monitor.monitor_thread.set_check_interval(120)
                    
        return HybridMonitor(self.order_widget, self.supabase_config, self.db_config)
        
    def get_current_monitor(self):
        """현재 활성 모니터 반환"""
        if not self.current_monitor:
            self.current_monitor = self.create_monitor()
        return self.current_monitor
        
    def switch_monitoring_method(self, method: str):
        """모니터링 방식 변경"""
        # 기존 모니터 중지
        if self.current_monitor:
            try:
                self.current_monitor.stop_monitoring()
            except:
                pass
                
        # 설정 업데이트
        self.config["monitoring"]["method"] = method
        
        # 새 모니터 생성 및 시작
        self.current_monitor = self.create_monitor()
        if self.current_monitor:
            self.current_monitor.start_monitoring()
            
        logging.info(f"모니터링 방식 변경: {method}")


def create_optimized_order_monitor(order_widget, supabase_config, db_config):
    """최적화된 주문 모니터 생성 헬퍼 함수"""
    factory = MonitoringFactory(order_widget, supabase_config, db_config)
    return factory.get_current_monitor() 