# -*- coding: utf-8 -*-
"""Common receipt printing utilities."""
from typing import Any, Dict
from datetime import datetime

def format_receipt_string(order: Dict[str, Any]) -> str:
    lines = []

    # 기본값 일관성 유지
    company_name = order.get('company_name', '')
    order_id = order.get('order_id', '')
    created_at = order.get('created_at', '')
    is_dine_in = order.get('is_dine_in', True)

    # Header
    lines.append("*** 손님 영수증 ***")
    lines.append(company_name)
    lines.append("")  # 빈 줄

    # Order info
    lines.append(f"주문번호: {order_id}")
    lines.append(f"주문일시: {created_at}")
    lines.append(f"주문유형:  {'매장 식사' if is_dine_in else '포장'}")
    lines.append("")  # 빈 줄

    lines.append("-" * 45)

    total = 0
    for item in order.get("items", []):
        name = item.get("name")
        order_item_id = item.get("order_item_id")
        qty = item.get("quantity", 0)
        price = item.get("price", 0)

        # 옵션 가격 계산
        options_price = sum(opt.get("price", 0) for opt in item.get("options", []))
        price_per_item = price + options_price  # 옵션 포함 개당 가격
        item_total = qty * price_per_item
        total += item_total

        item_line = f"상품명: {name}"
        if order_item_id:
            item_line += f" (ID:{order_item_id})"
        lines.append(item_line)

        for opt in item.get("options", []):
            opt_line = f" - 옵션: {opt['name']}"
            if opt.get("price", 0) > 0:
                opt_line += f" (+{opt['price']:,}원)"
            lines.append(opt_line)
            
        lines.append(f"수량: {qty}개")
        lines.append(f"단가: {price_per_item:,}원")
        lines.append(f"금액: {item_total:,}원")
        lines.append("")  # 아이템 간 빈 줄

    lines.append("-" * 32)
    lines.append(f"소계: {total:,}원")
    lines.append(f"총 금액: {total:,}원")
    lines.append("")  # 빈 줄
    lines.append("감사합니다!")
    lines.append("")  # 빈 줄

    current_time = datetime.now()
    lines.append(f"출력시간: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")  # 마지막 빈 줄

    return "\n".join(lines)
