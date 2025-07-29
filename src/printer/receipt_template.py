# -*- coding: utf-8 -*-
"""Common receipt printing utilities."""
from typing import Any, Dict
from datetime import datetime, timezone, timedelta
from collections import Counter
import logging

def format_datetime(datetime_str: str) -> str:
    """
    UTC ISO 형식의 datetime 문자열을 KST YYYY-MM-DD HH:mm 형식으로 변환합니다.
    
    Args:
        datetime_str: UTC ISO 형식의 datetime 문자열
        
    Returns:
        str: KST YYYY-MM-DD HH:mm 형식으로 포맷팅된 문자열
    """
    if not datetime_str:
        return ''
    
    try:
        # UTC 시간으로 파싱
        dt = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
        
        # 한국 시간(KST = UTC+9)으로 변환
        kst_offset = timedelta(hours=9)
        dt_kst = dt.replace(tzinfo=timezone.utc) + kst_offset
        
        # YYYY-MM-DD HH:mm 형식으로 포맷팅
        return dt_kst.strftime('%Y-%m-%d %H:%M')
    except (ValueError, TypeError) as e:
        logging.warning(f"날짜 파싱 실패: {datetime_str}, 에러: {e}")
        return datetime_str  # 파싱 실패시 원본 반환

def format_receipt_string(order: Dict[str, Any], receipt_type: str = "customer") -> str:
    """
    영수증 문자열을 포맷팅합니다.
    
    Args:
        order: 주문 데이터 딕셔너리
        receipt_type: 영수증 타입 ("customer": 손님용, "kitchen": 주방용)
        
    Returns:
        str: 포맷팅된 영수증 문자열
    """
    lines = []

    # 기본값 일관성 유지
    company_name = order.get('company_name', '')
    order_id = order.get('order_id', '')
    created_at = order.get('created_at', '')
    is_dine_in = order.get('is_dine_in', True)

    # 날짜 포맷팅
    formatted_datetime = format_datetime(created_at)

    # Header (영수증 타입에 따라 구분)
    if receipt_type == "kitchen":
        lines.append("*** 주방 주문서 ***")
    else:
        lines.append("*** 손님 영수증 ***")
    lines.append(company_name)
    lines.append("")  # 빈 줄

    # Order info
    lines.append(f"주문번호: {order_id}")
    lines.append(f"주문일시: {formatted_datetime}")
    lines.append(f"주문유형:  {'매장 식사' if is_dine_in else '포장'}")
    lines.append("")  # 빈 줄

    lines.append("-" * 20)

    # 데이터베이스의 total_price가 있으면 우선 사용, 없으면 개별 계산
    db_total_price = order.get("total_price")
    total = 0
    for item in order.get("items", []):
        name = item.get("name")
        order_item_id = item.get("order_item_id")
        qty = item.get("quantity", 0)
        
        # 옵션 표시용 집계 (가격 계산에는 사용하지 않음)
        options_list = item.get("options", [])
        option_counter = Counter()
        option_prices = {}
        
        for opt in options_list:
            opt_name = opt.get("name", "")
            opt_price = opt.get("price", 0)
            opt_quantity = opt.get("quantity", 1)  # 데이터베이스의 quantity 값 사용
            
            option_counter[opt_name] += opt_quantity  # quantity 값을 직접 더함
            option_prices[opt_name] = opt_price
        
        # 데이터베이스의 item_price 값을 직접 사용 (옵션 포함 단가)
        # 실제 데이터에서는 'price' 필드로 매핑됨
        price_per_item = item.get("price", 0)
        item_total = qty * price_per_item
        total += item_total

        # 상품명 표시
        item_line = f"상품명: {name}"
        if order_item_id:
            item_line += f" (ID:{order_item_id})"
        lines.append(item_line)

        # 옵션 표시 (개수와 함께) - 표시용만, 가격 계산과는 분리
        if option_counter:
            lines.append("  [선택된 옵션]")
            for opt_name, count in option_counter.items():
                opt_price = option_prices[opt_name]
                
                # 해당 옵션의 total_price 찾기
                opt_total_price = None
                for opt in options_list:
                    if opt.get("name") == opt_name:
                        opt_total_price = opt.get("total_price")
                        break
                
                # total_price가 있으면 사용, 없으면 단가 표시
                if opt_total_price is not None and opt_total_price > 0:
                    if count > 1:
                        lines.append(f"  - {opt_name} X {count} (+{opt_total_price:,}원)")
                    else:
                        lines.append(f"  - {opt_name} (+{opt_total_price:,}원)")
                else:
                    # 기존 로직 유지
                    if opt_price > 0:
                        lines.append(f"  - {opt_name} X {count} (+{opt_price:,}원)")
                    else:
                        lines.append(f"  - {opt_name}")
            
        lines.append(f"단가 (옵션포함): {price_per_item:,}원")
        lines.append(f"수량: {qty}개")
        lines.append(f"소계: {item_total:,}원")
        lines.append("")  # 아이템 간 빈 줄

    lines.append("-" * 20)
    
    # 총 금액 표시 (데이터베이스 total_price 우선 사용)
    if db_total_price is not None and db_total_price > 0:
        logging.info(f"영수증 템플릿({receipt_type}) - DB total_price 사용: {db_total_price:,}원")
        lines.append(f"총 금액: {db_total_price:,}원")
    else:
        logging.info(f"영수증 템플릿({receipt_type}) - 계산된 total 사용: {total:,}원")
        lines.append(f"총 금액: {total:,}원")
    
    lines.append("")  # 빈 줄
    lines.append("감사합니다!")
    lines.append("")  # 빈 줄
# 마지막 빈 줄
    return "\n".join(lines)