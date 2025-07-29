import json
import logging
from pathlib import Path
from typing import List
import win32print
from datetime import datetime, time
from src.error_logger import get_error_logger, log_exception

from src.printer.escpos_printer import print_receipt_esc_usb  # USB 프린터 출력 함수
from src.printer.file_printer import file_print_receipt  # 파일 프린터 출력 함수
from src.printer.com_printer import print_receipt_com, test_com_printer  # COM 포트 프린터 출력 함수

logger = logging.getLogger(__name__)


class PrinterManager:
    def __init__(self) -> None:
        # 프린터 설정 파일 경로
        self.config_file = Path("printer_config.json")
        self._customer_printer = {}
        self._kitchen_printer = {}
        self._auto_print_config = {}
        self.load_config()

    @property
    def printer_type(self) -> str:
        """현재 손님용 프린터 타입을 반환합니다. (기존 호환성)"""
        return self._customer_printer.get("printer_type", "escpos")

    @property
    def printer_name(self) -> str:
        """현재 손님용 프린터 이름을 반환합니다. (기존 호환성)"""
        return self._customer_printer.get("printer_name")

    @property
    def usb_info(self) -> dict:
        """현재 USB 정보를 반환합니다. (기존 호환성)"""
        return self._customer_printer.get("usb_info", {})

    def _get_default_config(self) -> dict:
        """기본 설정을 반환합니다."""
        try:
            default_printer = win32print.GetDefaultPrinter()
        except:
            default_printer = "기본 프린터"

        return {
            "customer_printer": {
                "printer_type": "escpos",
                "printer_name": default_printer,
                "usb_info": {
                    "vendor_id": "",
                    "product_id": "",
                    "interface": "0"
                }
            },
            "kitchen_printer": {
                "printer_type": "com",
                "com_port": "COM3",
                "baudrate": 9600,
                "enabled": True
            },
            "auto_print": {
                "enabled": False,
                "retry_count": 3,
                "retry_interval": 10,
                "check_printer_status": True
            }
        }

    def _validate_config(self, config: dict) -> bool:
        """설정 유효성을 검증합니다."""
        try:
            # 손님용 프린터 검증
            customer = config.get("customer_printer", {})
            printer_type = customer.get("printer_type")
            if printer_type not in ["escpos", "default"]:
                logger.warning(f"잘못된 손님용 프린터 타입: {printer_type}")
                return False

            if printer_type == "escpos":
                usb_info = customer.get("usb_info", {})
                vendor_id = usb_info.get("vendor_id", "")
                product_id = usb_info.get("product_id", "")
                if vendor_id and product_id:
                    # USB ID 형식 검증
                    try:
                        int(vendor_id, 16)
                        int(product_id, 16)
                    except ValueError:
                        logger.warning("잘못된 USB ID 형식")
                        return False

            # 주방용 프린터 검증
            kitchen = config.get("kitchen_printer", {})
            com_port = kitchen.get("com_port", "")
            baudrate = kitchen.get("baudrate", 9600)
            if com_port and not com_port.startswith("COM"):
                logger.warning(f"잘못된 COM 포트 형식: {com_port}")
                return False

            if not isinstance(baudrate, int) or baudrate <= 0:
                logger.warning(f"잘못된 baudrate: {baudrate}")
                return False

            return True
        except Exception as e:
            logger.error(f"설정 검증 오류: {e}")
            return False

    def load_config(self) -> None:
        """프린터 설정을 로드합니다."""
        default_config = self._get_default_config()
        
        if not self.config_file.exists():
            logger.info("설정 파일이 없어 기본 설정을 사용합니다.")
            self._apply_config(default_config)
            self.save_config()
            return

        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                config = json.load(f)

            if not self._validate_config(config):
                logger.warning("설정 파일이 유효하지 않아 기본 설정을 사용합니다.")
                self._apply_config(default_config)
                self.save_config()
                return

            # 누락된 설정은 기본값으로 보완
            for key, default_value in default_config.items():
                if key not in config:
                    config[key] = default_value
                elif isinstance(default_value, dict):
                    for sub_key, sub_default in default_value.items():
                        if sub_key not in config[key]:
                            config[key][sub_key] = sub_default

            self._apply_config(config)
            logger.info("설정 로드 완료")

        except Exception as e:
            logger.exception("설정 로드 오류: %s", e)
            logger.info("기본 설정을 사용합니다.")
            self._apply_config(default_config)
            self.save_config()

    def _apply_config(self, config: dict) -> None:
        """설정을 적용합니다."""
        self._customer_printer = config.get("customer_printer", {})
        self._kitchen_printer = config.get("kitchen_printer", {})
        self._auto_print_config = config.get("auto_print", {})
        
        logger.info(f"손님용 프린터 설정: {self._customer_printer}")
        logger.info(f"주방용 프린터 설정: {self._kitchen_printer}")

    def save_config(self) -> bool:
        """프린터 설정을 저장합니다."""
        try:
            config = {
                "customer_printer": self._customer_printer.copy(),
                "kitchen_printer": self._kitchen_printer.copy(),
                "auto_print": self._auto_print_config.copy()
            }
            
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            logger.info("설정 저장 완료")
            return True
        except Exception as e:
            logger.exception("설정 저장 오류: %s", e)
            return False

    def get_current_printer(self) -> str:
        """현재 선택된 프린터 이름을 반환합니다."""
        return self.printer_name

    def get_printer_type(self) -> str:
        """현재 프린터 타입을 반환합니다."""
        return self.printer_type

    def set_printer(self, name: str) -> bool:
        """프린터를 설정합니다."""
        self._customer_printer["printer_name"] = name
        return self.save_config()

    def set_usb_info(self, vendor_id: str, product_id: str, interface: str = "0") -> bool:
        """USB 프린터 정보 설정"""
        try:
            # USB ID 유효성 검증
            int(vendor_id, 16)
            int(product_id, 16)
            
            self._customer_printer["usb_info"] = {
                "vendor_id": vendor_id,
                "product_id": product_id,
                "interface": interface
            }
            return self.save_config()
        except ValueError as e:
            logger.error(f"잘못된 USB ID 형식: {e}")
            return False

    def set_customer_printer_type(self, printer_type: str, extra_info: dict = None) -> bool:
        """손님용 프린터 타입을 설정합니다."""
        if printer_type not in ["escpos", "default"]:
            logger.error(f"지원하지 않는 프린터 타입: {printer_type}")
            return False
        
        self._customer_printer["printer_type"] = printer_type
        
        if extra_info:
            if printer_type == "escpos":
                usb_info = {
                    "vendor_id": extra_info.get("vendor_id", ""),
                    "product_id": extra_info.get("product_id", ""),
                    "interface": extra_info.get("interface", "0")
                }
                # USB ID 유효성 검증
                if usb_info["vendor_id"] and usb_info["product_id"]:
                    try:
                        int(usb_info["vendor_id"], 16)
                        int(usb_info["product_id"], 16)
                        self._customer_printer["usb_info"] = usb_info
                    except ValueError:
                        logger.error("잘못된 USB ID 형식")
                        return False
        
        logger.info(f"손님용 프린터 타입 설정: {printer_type}")
        return self.save_config()

    def set_kitchen_printer_config(self, com_port: str = "COM3", baudrate: int = 9600, enabled: bool = True) -> bool:
        """주방용 프린터 설정을 업데이트합니다."""
        if not com_port.startswith("COM"):
            logger.error(f"잘못된 COM 포트 형식: {com_port}")
            return False
            
        if not isinstance(baudrate, int) or baudrate <= 0:
            logger.error(f"잘못된 baudrate: {baudrate}")
            return False
        
        self._kitchen_printer.update({
            "printer_type": "com",
            "com_port": com_port,
            "baudrate": baudrate,
            "enabled": enabled
        })
        return self.save_config()

    def get_customer_printer_config(self) -> dict:
        """손님용 프린터 설정을 반환합니다."""
        return self._customer_printer.copy()

    def get_kitchen_printer_config(self) -> dict:
        """주방용 프린터 설정을 반환합니다."""
        return self._kitchen_printer.copy()

    def test_kitchen_printer(self) -> bool:
        """주방용 프린터 연결을 테스트합니다."""
        com_port = self._kitchen_printer.get("com_port", "COM3")
        baudrate = self._kitchen_printer.get("baudrate", 9600)
        return test_com_printer(com_port, baudrate)

    def get_auto_print_config(self) -> dict:
        """자동 출력 설정을 반환합니다."""
        return self._auto_print_config.copy()

    def set_auto_print_config(self, config: dict) -> bool:
        """자동 출력 설정을 업데이트합니다."""
        logger.info(f"자동 출력 설정 업데이트: {config}")
        self._auto_print_config.update(config)
        return self.save_config()

    def is_auto_print_enabled(self) -> bool:
        """자동 출력이 활성화되어 있는지 확인합니다."""
        return self._auto_print_config.get("enabled", False)

    def should_auto_print(self, order_data: dict) -> bool:
        """주문이 자동 출력 조건을 만족하는지 확인합니다."""
        order_id = order_data.get("order_id", "N/A")
        
        if not self.is_auto_print_enabled():
            logger.info(f"주문 {order_id}: 자동 출력이 비활성화되어 있음")
            return False
        
        # 이미 출력된 주문인지 확인
        if order_data.get("is_printed", False):
            logger.info(f"주문 {order_id}: 이미 출력됨")
            return False
                
        logger.info(f"주문 {order_id}: 자동 출력 조건을 만족함")
        return True

    def check_printer_status(self) -> bool:
        """프린터 상태를 확인합니다."""
        if not self._auto_print_config.get("check_printer_status", True):
            return True
            
        try:
            printer_type = self.printer_type
            
            if printer_type == "default":
                # 윈도우 프린터 상태 확인
                flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
                printers = [p[2] for p in win32print.EnumPrinters(flags)]
                return self.printer_name in printers
                
            elif printer_type == "escpos":
                # ESC/POS 프린터의 경우 USB 정보가 있는지 확인
                usb_info = self.usb_info
                vendor_id = usb_info.get("vendor_id")
                product_id = usb_info.get("product_id")
                if not vendor_id or not product_id:
                    logger.warning("ESC/POS 프린터의 USB 정보가 설정되지 않았습니다.")
                    return False
                return True
                
            else:
                logger.warning(f"알 수 없는 프린터 타입: {printer_type}")
                return False
                
        except Exception as e:
            logger.error(f"프린터 상태 확인 오류: {e}")
            return False

    def print_customer_receipt(self, order_data: dict) -> bool:
        """손님용 영수증을 출력합니다."""
        printer_type = self.printer_type
        success = False
        error_msg = None

        logger.info(f"손님용 프린터 출력 시작 - 타입: {printer_type}")

        try:
            if printer_type == "escpos":
                usb_info = self.usb_info
                vendor_id = usb_info.get("vendor_id")
                product_id = usb_info.get("product_id")
                
                if not vendor_id or not product_id:
                    error_msg = "ESC/POS 프린터 USB 정보가 설정되지 않았습니다."
                else:
                    try:
                        vendor_id_int = int(vendor_id, 16)
                        product_id_int = int(product_id, 16)
                        interface = int(usb_info.get("interface", "0"))
                        
                        logger.info(f"ESC/POS 프린터 연결 시도: VID={vendor_id_int:04X}, PID={product_id_int:04X}")
                        
                        success = print_receipt_esc_usb(
                            order_data,
                            vendor_id_int,
                            product_id_int,
                            interface
                        )
                        
                        if success:
                            logger.info("손님용 ESC/POS 프린터 출력 성공")
                        else:
                            error_msg = "ESC/POS 프린터 연결 실패"
                            
                    except ValueError as e:
                        error_msg = f"USB ID 변환 오류: {e}"
                        
            elif printer_type == "default":
                printer_name = self.printer_name
                if not printer_name:
                    error_msg = "윈도우 프린터 이름이 설정되지 않았습니다."
                else:
                    logger.info(f"윈도우 프린터 출력 시도: {printer_name}")
                    success = print_receipt_win(order_data, printer_name)
                    if not success:
                        error_msg = f"윈도우 프린터({printer_name}) 출력 실패"
            else:
                error_msg = f"지원하지 않는 프린터 타입: {printer_type}"

        except Exception as e:
            error_msg = f"프린터 출력 중 예외 발생: {e}"
            logger.exception(error_msg)

        # 실패 시 오류 로그 작성
        if error_msg:
            logger.error(error_msg)
            error_logger = get_error_logger()
            if error_logger:
                error_logger.log_printer_error(
                    printer_type=printer_type,
                    error=Exception(error_msg),
                    order_id=order_data.get('order_id', 'Unknown')
                )

        # 파일로 백업 출력 (손님용)
        file_success = file_print_receipt(order_data, "customer")
        if file_success:
            logger.info("손님용 파일 프린터 출력 성공")
        else:
            logger.error("손님용 파일 프린터 출력 실패")

        logger.info(f"손님용 프린터 출력 결과: 실제프린터={success}, 파일={file_success}")
        return success

    def print_kitchen_receipt(self, order_data: dict) -> bool:
        """주방용 영수증을 출력합니다."""
        kitchen_config = self._kitchen_printer
        
        # 주방 프린터가 비활성화된 경우
        if not kitchen_config.get("enabled", True):
            logger.info("주방 프린터가 비활성화되어 있습니다.")
            return True

        com_port = kitchen_config.get("com_port", "COM3")
        baudrate = kitchen_config.get("baudrate", 9600)
        
        try:
            success = print_receipt_com(order_data, com_port, baudrate)
            if success:
                logger.info(f"주방용 영수증 출력 성공: {com_port}")
            else:
                logger.error(f"주방용 COM 포트 프린터({com_port}) 출력 실패")
                error_logger = get_error_logger()
                if error_logger:
                    error_logger.log_printer_error(
                        printer_type="com_kitchen",
                        error=Exception(f"주방용 COM 포트 프린터({com_port}) 출력 실패"),
                        order_id=order_data.get('order_id', 'Unknown')
                    )
            
            # 파일로 백업 출력 (주방용)
            file_success = file_print_receipt(order_data, "kitchen")
            if file_success:
                logger.info("주방용 파일 프린터 출력 성공")
            else:
                logger.error("주방용 파일 프린터 출력 실패")
            
            logger.info(f"주방용 프린터 출력 결과: 실제프린터={success}, 파일={file_success}")
            return success
        except Exception as e:
            logger.exception(f"주방용 영수증 출력 중 예외 발생: {e}")
            return False

    def print_both_receipts(self, order_data: dict) -> dict:
        """손님용과 주방용 영수증을 모두 출력합니다."""
        results = {
            "customer": False,
            "kitchen": False
        }
        
        # 손님용 영수증 출력
        try:
            results["customer"] = self.print_customer_receipt(order_data)
        except Exception as e:
            logger.error(f"손님용 영수증 출력 오류: {e}")
            results["customer"] = False

        # 주방용 영수증 출력
        try:
            results["kitchen"] = self.print_kitchen_receipt(order_data)
        except Exception as e:
            logger.error(f"주방용 영수증 출력 오류: {e}")
            results["kitchen"] = False

        return results

    # 기존 호환성을 위한 메서드들
    def print_receipt(self, order_data: dict) -> bool:
        """주문 데이터를 기반으로 영수증을 출력합니다. (기존 호환성 유지)"""
        return self.print_customer_receipt(order_data)

    def set_printer_type(self, printer_type: str, extra_info: dict = None) -> bool:
        """프린터 타입을 설정합니다. (기존 호환성 유지)"""
        return self.set_customer_printer_type(printer_type, extra_info)

    @staticmethod
    def list_printers() -> List[str]:
        """사용 가능한 프린터 목록을 반환합니다."""
        try:
            flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
            return [p[2] for p in win32print.EnumPrinters(flags)]
        except Exception as e:
            logger.error(f"프린터 목록 조회 오류: {e}")
            return []

    @staticmethod
    def get_default_printer() -> str:
        """기본 프린터 이름을 반환합니다."""
        try:
            return win32print.GetDefaultPrinter()
        except Exception as e:
            logger.error(f"기본 프린터 조회 오류: {e}")
            return "기본 프린터"