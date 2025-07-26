import logging
import os
import sys
from src.printer.receipt_template import format_receipt_string
import win32print
import win32ui

# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('printer_debug.log', mode='a', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

def print_receipt(order_data: dict) -> bool:
    """주문 데이터를 기반으로 파일로 영수증 출력"""
    try:
        logger.info("파일 프린터로 영수증 출력 시작")

        # 출력 디렉토리 설정
        current_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(current_dir, "output")
        os.makedirs(output_dir, exist_ok=True)

        output_file = os.path.join(output_dir, "test_receipt_output.bin")
        logger.debug(f"출력 파일 경로: {output_file}")

        # 기존 파일 삭제
        if os.path.exists(output_file):
            os.remove(output_file)
            logger.debug("기존 출력 파일 삭제됨")

        # 영수증 텍스트 생성 및 파일 저장
        receipt_text = format_receipt_string(order_data, "customer")
        with open(output_file, "wb") as f:
            f.write(receipt_text.encode("cp949"))
            logger.debug("영수증 텍스트 파일로 저장 완료 (cp949 인코딩)")

        logger.info(f"영수증 파일 생성 완료 (크기: {os.path.getsize(output_file)} bytes)")
        return True

    except Exception as e:
        logger.exception("파일 프린터 오류: %s", e)
        return False

def print_receipt_win(order_data: dict, printer_name: str = None) -> bool:
    """윈도우 프린터로 영수증을 출력합니다."""
    try:
        # 디버깅: 손님 프린터(Windows)로 전달된 데이터 로깅
        logger.info(f"손님 프린터(Windows) 데이터 - order_id: {order_data.get('order_id')}")
        logger.info(f"손님 프린터(Windows) 데이터 - total_price: {order_data.get('total_price')}")
        logger.info(f"손님 프린터(Windows) 데이터 - items 개수: {len(order_data.get('items', []))}")
        
        receipt_text = format_receipt_string(order_data, "customer")
        if not printer_name:
            printer_name = win32print.GetDefaultPrinter()
        hprinter = win32print.OpenPrinter(printer_name)
        hdc = None
        try:
            hprinter_info = win32print.GetPrinter(hprinter, 2)
            pdc = win32ui.CreateDC()
            pdc.CreatePrinterDC(printer_name)
            pdc.StartDoc('POS Receipt')
            pdc.StartPage()
            # 텍스트 출력 (간단하게)
            pdc.TextOut(100, 100, receipt_text)
            pdc.EndPage()
            pdc.EndDoc()
            pdc.DeleteDC()
        finally:
            win32print.ClosePrinter(hprinter)
        return True
    except Exception as e:
        logger.exception("윈도우 프린터 출력 오류: %s", e)
        return False
