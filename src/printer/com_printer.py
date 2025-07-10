# -*- coding: utf-8 -*-
"""COM 포트 시리얼 프린터 출력 모듈."""
import serial
import logging
from typing import Dict, Any
from src.printer.receipt_template import format_receipt_string

logger = logging.getLogger(__name__)

def print_receipt_com(order_data: Dict[str, Any], com_port: str = "COM3", baudrate: int = 9600, timeout: int = 5) -> bool:
    """
    COM 포트를 통해 시리얼 프린터로 영수증을 출력합니다.
    
    Args:
        order_data: 주문 데이터 딕셔너리
        com_port: COM 포트 (예: "COM3")
        baudrate: 통신 속도 (기본값: 9600)
        timeout: 타임아웃 (초)
        
    Returns:
        bool: 출력 성공 여부
    """
    try:
        logger.info(f"COM 포트 프린터 출력 시작: {com_port}")
        
        # 영수증 텍스트 생성
        receipt_text = format_receipt_string(order_data)
        
        # 시리얼 포트 연결
        with serial.Serial(com_port, baudrate, timeout=timeout) as ser:
            if not ser.is_open:
                logger.error(f"COM 포트 {com_port} 열기 실패")
                return False
                
            logger.info(f"COM 포트 {com_port} 연결 성공")
            
            # 텍스트를 바이트로 변환하여 전송
            # 한글 인코딩 처리 (CP949 또는 UTF-8)
            try:
                receipt_bytes = receipt_text.encode('cp949')
            except UnicodeEncodeError:
                # CP949로 인코딩할 수 없는 경우 UTF-8 사용
                receipt_bytes = receipt_text.encode('utf-8')
            
            # 프린터 제어 명령어 추가 (ESC/POS 호환)
            esc_commands = b'\x1b\x40'  # 프린터 초기화
            esc_commands += b'\x1b\x61\x00'  # 왼쪽 정렬
            esc_commands += b'\x1b\x45\x01'  # 볼드체 켜기
            esc_commands += b'\x1d\x21\x11'  # 가로/세로 2배 크기
            
            # 제어 명령어 + 영수증 내용 + 용지 컷팅 명령어
            # 출력 후 볼드 및 크기 리셋
            reset_commands = b'\x1b\x45\x00'  # 볼드체 끄기
            reset_commands += b'\x1d\x21\x00'  # 정상 크기로 복원
            
            full_data = esc_commands + receipt_bytes + reset_commands + b'\x1d\x56\x00'  # 부분 컷팅
            
            # 데이터 전송
            ser.write(full_data)
            ser.flush()  # 버퍼 플러시
            
            logger.info(f"COM 포트 {com_port}로 영수증 출력 완료 (볼드체, 큰 글자)")
            return True
            
    except serial.SerialException as e:
        logger.error(f"시리얼 포트 오류 ({com_port}): {e}")
        return False
    except Exception as e:
        logger.error(f"COM 포트 프린터 출력 오류 ({com_port}): {e}")
        return False

def test_com_printer(com_port: str = "COM3", baudrate: int = 9600) -> bool:
    """
    COM 포트 프린터 연결 테스트
    
    Args:
        com_port: COM 포트
        baudrate: 통신 속도
        
    Returns:
        bool: 연결 테스트 성공 여부
    """
    try:
        with serial.Serial(com_port, baudrate, timeout=2) as ser:
            if ser.is_open:
                # 간단한 테스트 메시지 전송 (볼드, 큰 글자로)
                esc_commands = b'\x1b\x40'  # 초기화
                esc_commands += b'\x1b\x45\x01'  # 볼드체 켜기
                esc_commands += b'\x1d\x21\x11'  # 가로/세로 2배 크기
                
                test_message = "프린터 연결 테스트\n\n\n"
                test_bytes = test_message.encode('cp949')
                
                reset_commands = b'\x1b\x45\x00'  # 볼드체 끄기
                reset_commands += b'\x1d\x21\x00'  # 정상 크기로 복원
                
                full_data = esc_commands + test_bytes + reset_commands
                
                ser.write(full_data)
                ser.flush()
                logger.info(f"COM 포트 {com_port} 연결 테스트 성공 (볼드체, 큰 글자)")
                return True
            else:
                logger.error(f"COM 포트 {com_port} 열기 실패")
                return False
    except Exception as e:
        logger.error(f"COM 포트 {com_port} 연결 테스트 실패: {e}")
        return False

def print_kitchen_receipt_com(order_data: Dict[str, Any], com_port: str = "COM3", baudrate: int = 9600) -> bool:
    """
    주방용 영수증을 COM 포트로 출력합니다.
    
    Args:
        order_data: 주문 데이터
        com_port: COM 포트
        baudrate: 통신 속도
        
    Returns:
        bool: 출력 성공 여부
    """
    try:
        logger.info(f"주방용 영수증 COM 포트 출력 시작: {com_port}")
        
        # 주방용 영수증 포맷으로 생성 -> 손님용과 동일한 포맷으로 변경
        receipt_text = format_receipt_string(order_data)
        
        # 시리얼 포트 연결 및 출력
        with serial.Serial(com_port, baudrate, timeout=5) as ser:
            if not ser.is_open:
                logger.error(f"주방 프린터 COM 포트 {com_port} 열기 실패")
                return False
            
            # 텍스트 인코딩
            try:
                receipt_bytes = receipt_text.encode('cp949')
            except UnicodeEncodeError:
                receipt_bytes = receipt_text.encode('utf-8')
            
            # ESC/POS 명령어 (주방용도 볼드, 큰 글자로)
            esc_commands = b'\x1b\x40'  # 초기화
            esc_commands += b'\x1b\x61\x00'  # 왼쪽 정렬
            esc_commands += b'\x1b\x45\x01'  # 볼드체 켜기
            esc_commands += b'\x1d\x21\x11'  # 가로/세로 2배 크기
            
            # 출력 후 리셋
            reset_commands = b'\x1b\x45\x00'  # 볼드체 끄기
            reset_commands += b'\x1d\x21\x00'  # 정상 크기로 복원
            
            # 전체 데이터
            full_data = esc_commands + receipt_bytes + reset_commands + b'\x1d\x56\x00'  # 부분 컷팅
            
            # 데이터 전송
            ser.write(full_data)
            ser.flush()
            print(full_data)
            
            logger.info(f"주방용 영수증 COM 포트 {com_port} 출력 완료 (볼드체, 큰 글자)")
            return True
            
    except Exception as e:
        logger.error(f"주방용 영수증 COM 포트 출력 오류 ({com_port}): {e}")
        return False 