import logging
import os
import sys
from datetime import datetime
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

def file_print_receipt(order_data: dict, receipt_type: str = "customer") -> bool:
    """주문 데이터를 기반으로 파일로 영수증 출력
    
    Args:
        order_data: 주문 데이터 딕셔너리
        receipt_type: 영수증 타입 ("customer": 손님용, "kitchen": 주방용)
        
    Returns:
        bool: 출력 성공 여부
    """
    try:
        logger.info(f"파일 프린터로 {receipt_type} 영수증 출력 시작")

        # 출력 디렉토리 설정
        current_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(current_dir, "output")
        os.makedirs(output_dir, exist_ok=True)

        # 타임스탬프 생성
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        order_id = order_data.get('order_id', 'unknown')
        
        # 파일명 설정 (타입별로 구분)
        if receipt_type == "kitchen":
            output_file = os.path.join(output_dir, f"kitchen_receipt_{order_id}_{timestamp}.txt")
        else:
            output_file = os.path.join(output_dir, f"customer_receipt_{order_id}_{timestamp}.txt")
            
        logger.debug(f"출력 파일 경로: {output_file}")

        # 영수증 텍스트 생성 및 파일 저장
        receipt_text = format_receipt_string(order_data, receipt_type)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(receipt_text)
            f.write(f"\n\n=== 파일 프린터 정보 ===\n")
            f.write(f"영수증 타입: {receipt_type}\n")
            f.write(f"생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"주문 ID: {order_id}\n")
            logger.debug(f"{receipt_type} 영수증 텍스트 파일로 저장 완료 (UTF-8 인코딩)")

        logger.info(f"{receipt_type} 영수증 파일 생성 완료 (크기: {os.path.getsize(output_file)} bytes)")
        return True

    except Exception as e:
        logger.exception("파일 프린터 오류: %s", e)
        return False

def save_printer_raw_data(data: bytes, printer_type: str, order_data: dict, receipt_type: str = "customer") -> bool:
    """프린터에 전송되는 원시 바이트 데이터를 파일로 저장
    
    Args:
        data: 프린터에 전송될 원시 바이트 데이터
        printer_type: 프린터 타입 ("com", "escpos")
        order_data: 주문 데이터 딕셔너리
        receipt_type: 영수증 타입 ("customer": 손님용, "kitchen": 주방용)
        
    Returns:
        bool: 저장 성공 여부
    """
    try:
        logger.info(f"{printer_type} 프린터의 원시 데이터를 파일로 저장 시작")

        # 출력 디렉토리 설정
        current_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(current_dir, "output", "raw_data")
        os.makedirs(output_dir, exist_ok=True)

        # 타임스탬프 생성
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        order_id = order_data.get('order_id', 'unknown')
        
        # 파일명 설정
        raw_file = os.path.join(output_dir, f"{printer_type}_{receipt_type}_raw_{order_id}_{timestamp}.bin")
        text_file = os.path.join(output_dir, f"{printer_type}_{receipt_type}_raw_{order_id}_{timestamp}.txt")
        
        # 원시 바이트 데이터 저장
        with open(raw_file, "wb") as f:
            f.write(data)
            
        # 읽기 쉬운 형태로도 저장 (헥스 덤프)
        with open(text_file, "w", encoding="utf-8") as f:
            f.write(f"=== {printer_type.upper()} 프린터 원시 데이터 ({receipt_type}) ===\n")
            f.write(f"주문 ID: {order_id}\n")
            f.write(f"생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"데이터 크기: {len(data)} bytes\n\n")
            
            f.write("=== 헥스 덤프 ===\n")
            for i in range(0, len(data), 16):
                chunk = data[i:i+16]
                hex_part = ' '.join(f'{b:02X}' for b in chunk)
                ascii_part = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
                f.write(f"{i:08X}: {hex_part:<48} |{ascii_part}|\n")
                
            f.write("\n=== ESC/POS 명령어 분석 ===\n")
            # ESC/POS 명령어 분석
            i = 0
            while i < len(data):
                if data[i] == 0x1B and i + 1 < len(data):  # ESC
                    if data[i+1] == 0x40:
                        f.write(f"위치 {i:04X}: ESC @ (프린터 초기화)\n")
                        i += 2
                    elif data[i+1] == 0x61:
                        if i + 2 < len(data):
                            align = {0: "왼쪽", 1: "가운데", 2: "오른쪽"}.get(data[i+2], "알 수 없음")
                            f.write(f"위치 {i:04X}: ESC a {data[i+2]} ({align} 정렬)\n")
                            i += 3
                        else:
                            i += 2
                    elif data[i+1] == 0x45:
                        if i + 2 < len(data):
                            bold = "켜기" if data[i+2] else "끄기"
                            f.write(f"위치 {i:04X}: ESC E {data[i+2]} (볼드체 {bold})\n")
                            i += 3
                        else:
                            i += 2
                    else:
                        i += 1
                elif data[i] == 0x1D and i + 1 < len(data):  # GS
                    if data[i+1] == 0x21:
                        if i + 2 < len(data):
                            f.write(f"위치 {i:04X}: GS ! {data[i+2]:02X} (글자 크기 설정)\n")
                            i += 3
                        else:
                            i += 2
                    elif data[i+1] == 0x56:
                        f.write(f"위치 {i:04X}: GS V (용지 자르기)\n")
                        i += 2
                    else:
                        i += 1
                elif data[i] == 0x0A:
                    f.write(f"위치 {i:04X}: LF (줄바꿈)\n")
                    i += 1
                elif data[i] == 0x0D:
                    f.write(f"위치 {i:04X}: CR (캐리지 리턴)\n")
                    i += 1
                else:
                    i += 1

        logger.info(f"{printer_type} 원시 데이터 저장 완료: {raw_file}, {text_file}")
        return True

    except Exception as e:
        logger.exception(f"{printer_type} 원시 데이터 저장 오류: %s", e)
        return False