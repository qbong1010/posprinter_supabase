# -*- coding: utf-8 -*-
"""Common receipt printing utilities."""
from typing import Any, Dict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from collections import Counter

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

    # 주문일시 포맷팅 (UTC -> KST)
    if created_at:
        try:
            created_at_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            if created_at_dt.tzinfo is None:
                created_at_dt = created_at_dt.replace(tzinfo=timezone.utc)
            created_at_dt = created_at_dt.astimezone(ZoneInfo('Asia/Seoul'))
            formatted_created_at = created_at_dt.strftime('%Y-%m-%d %H:%M')
        except Exception:
            formatted_created_at = created_at
    else:
        formatted_created_at = ''

    # Header (영수증 타입에 따라 구분)
    if receipt_type == "kitchen":
        lines.append("*** 주방 주문서 ***")
    else:
        lines.append("*** 손님 영수증 ***")
    lines.append(company_name)
    lines.append("")  # 빈 줄

    # Order info
    lines.append(f"주문번호: {order_id}")
    lines.append(f"주문일시: {formatted_created_at}")
    lines.append(f"주문유형:  {'매장 식사' if is_dine_in else '포장'}")
    lines.append("")  # 빈 줄

    lines.append("-" * 20)

    total = 0
    for item in order.get("items", []):
        name = item.get("name")
        order_item_id = item.get("order_item_id")
        qty = item.get("quantity", 0)
        price = item.get("price", 0)

        # 옵션 개수 집계 (같은 이름의 옵션을 카운트)
        options_list = item.get("options", [])
        option_counter = Counter()
        option_prices = {}
        
        for opt in options_list:
            opt_name = opt.get("name", "")
            opt_price = opt.get("price", 0)
            option_counter[opt_name] += 1
            option_prices[opt_name] = opt_price

        # 옵션 총 가격 계산 (각 옵션의 개수 × 가격)
        options_price = sum(
            option_counter[opt_name] * opt_price 
            for opt_name, opt_price in option_prices.items()
        )
        
        price_per_item = price + options_price  # 옵션 포함 개당 가격
        item_total = qty * price_per_item
        total += item_total

        # 상품명 표시
        item_line = f"상품명: {name}"
        if order_item_id:
            item_line += f" (ID:{order_item_id})"
        lines.append(item_line)

        # 옵션 표시 (개수와 함께)
        if option_counter:
            lines.append("  [선택된 옵션]")
            for opt_name, count in option_counter.items():
                opt_price = option_prices[opt_name]
                
                # 항상 개수를 표시하는 새로운 형태
                if opt_price > 0:
                    lines.append(f"  - {opt_name}(+{opt_price:,}원) {count}개")
                else:
                    lines.append(f"  - {opt_name} {count}개")
            
        lines.append(f"수량: {qty}개")
        lines.append(f"단가 (옵션포함): {price_per_item:,}원")
        lines.append(f"소계: {item_total:,}원")
        lines.append("")  # 아이템 간 빈 줄

    lines.append("-" * 20)
    lines.append(f"총 금액: {total:,}원")
    lines.append("")  # 빈 줄
    lines.append("감사합니다!")
    lines.append("")  # 빈 줄

    current_time = datetime.now(ZoneInfo('Asia/Seoul'))
    lines.append(f"출력시간: {current_time.strftime('%Y-%m-%d %H:%M')}")
    lines.append("")  # 마지막 빈 줄

    return "\n".join(lines)

def format_kitchen_receipt_string(order: Dict[str, Any]) -> str:
    """주방용 영수증 문자열을 포맷팅합니다."""
    return format_receipt_string(order, "kitchen")
