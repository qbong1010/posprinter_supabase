import logging
import os
import time
from src.printer.receipt_template import format_receipt_string
from src.error_logger import get_error_logger

# USB 프린터 관련 모듈 import (에러 발생 시 우회)
try:
    from escpos.printer import Usb
    import usb.backend.libusb1
    USB_PRINTER_AVAILABLE = True
except ImportError as e:
    USB_PRINTER_AVAILABLE = False
    print(f"⚠️ USB 프린터 모듈 로드 실패: {e}")
    print("   USB 프린터 기능은 비활성화됩니다.")
    # 더미 클래스 정의
    class Usb:
        def __init__(self, *args, **kwargs):
            pass

logger = logging.getLogger(__name__)

# ESC/POS 프린터 스타일 명령어
STYLE_COMMANDS = {
    'init': b'\x1b\x40',  # 프린터 초기화
    'center': b'\x1b\x61\x01',  # 가운데 정렬
    'left': b'\x1b\x61\x00',  # 왼쪽 정렬
    'right': b'\x1b\x61\x02',  # 오른쪽 정렬
    'text_2x': b'\x1d\x21\x11',  # 글자 크기 2배
    'text_normal': b'\x1d\x21\x00',  # 기본 글자 크기
    'cut': b'\x1d\x56\x41\x00',  # 용지 자르기
    'line_feed': b'\x0a',  # 줄바꿈 (LF)
    'carriage_return': b'\x0d',  # 캐리지 리턴 (CR)
    'crlf': b'\x0d\x0a'  # CR+LF
}

def debug_save_receipt_text(receipt_text: str, filename: str = "debug_receipt.txt"):
    """디버깅을 위해 영수증 텍스트를 파일로 저장합니다."""
    try:
        output_dir = os.path.join("src", "printer", "output")
        os.makedirs(output_dir, exist_ok=True)
        
        filepath = os.path.join(output_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(receipt_text)
            f.write(f"\n\n=== 디버그 정보 ===\n")
            f.write(f"총 문자 수: {len(receipt_text)}\n")
            f.write(f"줄 수: {len(receipt_text.split(chr(10)))}\n")
            lines = receipt_text.split('\n')
            for i, line in enumerate(lines):
                f.write(f"줄 {i+1:2d}: '{line}' (길이: {len(line)})\n")
        
        logger.info(f"영수증 텍스트를 디버그 파일에 저장: {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"디버그 파일 저장 중 오류: {e}")
        return None

def print_receipt_esc_usb(order, vendor_id, product_id, interface, codepage=0x13):
    """libusb DLL을 사용하여 USB 프린터로 영수증을 출력합니다.
    
    Args:
        order: 주문 정보 딕셔너리
        vendor_id: USB 벤더 ID
        product_id: USB 제품 ID
        interface: USB 인터페이스 번호
        codepage: 프린터 코드페이지 (기본값: 0x13 = 19)
            - 0x03 (3): CP949 / 완성형 한글
            - 0x13 (19): CP949 / 조합형 한글
    """
    # USB 프린터 모듈이 사용 불가능한 경우
    if not USB_PRINTER_AVAILABLE:
        error_msg = "USB 프린터 모듈이 로드되지 않아 출력할 수 없습니다."
        logger.error(error_msg)
        # Supabase에도 에러 로깅
        error_logger = get_error_logger()
        if error_logger:
            error_logger.log_printer_error(
                printer_type="escpos_usb",
                error=Exception(error_msg),
                order_id=order.get('order_id', 'Unknown')
            )
        return False
    
    try:
        receipt_text = format_receipt_string(order)
        
        # 디버깅을 위해 텍스트 저장
        debug_save_receipt_text(receipt_text, f"receipt_{order.get('order_id', 'test')}.txt")
        
    except Exception as e:
        logger.error(f"영수증 텍스트 포맷팅 중 오류 발생: {e}")
        # Supabase에도 에러 로깅
        error_logger = get_error_logger()
        if error_logger:
            error_logger.log_printer_error(
                printer_type="escpos_usb",
                error=e,
                order_id=order.get('order_id', 'Unknown')
            )
        return False

    # libusb DLL을 루트 디렉토리에서 로드
    try:
        # 프로젝트 루트 디렉토리 경로 계산 (현재 파일에서 2단계 위로)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.dirname(os.path.dirname(current_dir))
        libusb_path = os.path.join(root_dir, "libusb-1.0.dll")
        
        backend = usb.backend.libusb1.get_backend(find_library=lambda x: libusb_path)

    except Exception as e:
        error_msg = f"libusb 백엔드 생성 실패: {e}"
        logger.error(error_msg)
        # Supabase에도 에러 로깅
        error_logger = get_error_logger()
        if error_logger:
            error_logger.log_printer_error(
                printer_type="escpos_usb",
                error=e,
                order_id=order.get('order_id', 'Unknown')
            )
        return False

    if backend is None:
        logger.error("libusb-1.0.dll을 로드할 수 없습니다. 백엔드 생성 실패.")
        return False

    printer = None
    try:
        # 백엔드를 명시적으로 전달
        logger.info(f"USB 프린터 연결 시도: vID=0x{vendor_id:04x}, pID=0x{product_id:04x}, interface={interface}")
        printer = Usb(idVendor=vendor_id, idProduct=product_id, interface=interface, backend=backend)
        logger.info("USB 프린터 객체 생성 성공. 데이터 전송을 시작합니다.")
        
        # 프린터 초기화 및 인코딩 설정
        printer._raw(STYLE_COMMANDS['init'])  # 프린터 초기화
        printer._raw(bytes([0x1b, 0x74, codepage]))  # 코드페이지 설정
        printer.encoding = 'cp949'  # python-escpos의 인코딩 속성 지정

        # 영수증 텍스트를 CP949로 직접 인코딩하여 바이트로 전송
        lines = receipt_text.split('\n')
        
        # 디버깅을 위한 로그 추가
        logger.info(f"영수증 총 줄 수: {len(lines)}")
        logger.debug(f"영수증 전체 텍스트:\n{receipt_text}")
        
        for i, line in enumerate(lines):
            # 빈 줄 처리
            if not line.strip():
                printer._raw(STYLE_COMMANDS['crlf'])
                time.sleep(0.01)  # 10ms 지연
                continue
                
            logger.debug(f"처리 중인 줄 {i+1}: {line}")
            
            if '주문번호' in line:
                printer._raw(STYLE_COMMANDS['center'])  # 가운데 정렬
                time.sleep(0.01)
                printer._raw(STYLE_COMMANDS['text_2x'])  # 글자 크기 2배
                time.sleep(0.01)
                printer._raw(line.encode('cp949', errors='strict'))
                printer._raw(STYLE_COMMANDS['crlf'])  # CR+LF로 줄바꿈
                time.sleep(0.02)  # 큰 텍스트는 조금 더 기다림
                printer._raw(STYLE_COMMANDS['text_normal'])  # 기본 글자 크기
                time.sleep(0.01)
                printer._raw(STYLE_COMMANDS['left'])  # 왼쪽 정렬
                time.sleep(0.01)
            else:
                printer._raw(line.encode('cp949', errors='strict'))
                printer._raw(STYLE_COMMANDS['crlf'])  # CR+LF로 줄바꿈
                time.sleep(0.01)  # 10ms 지연
        
        # 추가 줄바꿈으로 여백 확보
        printer._raw(STYLE_COMMANDS['crlf'])
        time.sleep(0.02)
        printer._raw(STYLE_COMMANDS['crlf'])
        time.sleep(0.02)
        
        # 용지 자르기 전에 충분한 시간 대기
        time.sleep(0.1)
        printer._raw(STYLE_COMMANDS['cut'])  # 용지 자르기
        time.sleep(0.05)  # 자르기 완료 대기

        logger.info(f"USB 프린터(vID={vendor_id:04x}, pID={product_id:04x})로 영수증 전송 완료")
        return True

    except UnicodeEncodeError as e:
        logger.error(f"텍스트 인코딩 중 오류 발생: {e}", exc_info=True)
        logger.error(f"인코딩 실패한 텍스트: {receipt_text}")
        return False
    except PermissionError as e:
        logger.error(f"USB 접근 권한이 없습니다: {e}", exc_info=True)
    except usb.core.USBError as e:
        logger.error(f"USB 통신 오류. VID/PID, 드라이버(Zadig) 또는 다른 프로그램의 점유 상태를 확인하세요: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"USB 프린터 출력 중 알 수 없는 오류 발생: {e}", exc_info=True)
        return False
    finally:
        if printer:
            try:
                printer.close()
                logger.info("프린터 연결을 닫았습니다.")
            except Exception as close_e:
                logger.error(f"프린터 연결을 닫는 중 오류 발생: {close_e}")

    return False