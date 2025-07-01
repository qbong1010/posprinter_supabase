import os
import logging
from typing import Any, Dict, List, Optional

import requests
from PySide6.QtCore import QObject, Signal
from src.error_logger import get_error_logger

logger = logging.getLogger(__name__)

class SupabaseClient(QObject):
    """Supabase 데이터베이스와 연동하여 주문 데이터를 가져옵니다."""

    def __init__(self) -> None:
        super().__init__()
        project_id = os.getenv("SUPABASE_PROJECT_ID")
        self.base_url = os.getenv("SUPABASE_URL") or f"https://{project_id}.supabase.co"
        self.api_key = os.getenv("SUPABASE_API_KEY")
        self.headers = {
            "apikey": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
        }

    def get_orders(self, limit: int = 10) -> List[Dict[str, Any]]:
        """최근 주문 목록을 가져옵니다."""
        try:
            # 주문 기본 정보 조회
            params = {
                "select": """
                    order_id,
                    company_id,
                    is_dine_in,
                    total_price,
                    created_at,
                    is_printed,
                    company!inner(company_name),
                    order_items!inner(
                        order_item_id,
                        quantity,
                        item_price,
                        menu_item!inner(menu_name),
                        options!inner(
                            option_item!inner(
                                option_item_name,
                                option_price
                            )
                        )
                    )
                """,
                "order": "created_at.desc",
                "limit": str(limit),
            }
            resp = requests.get(f"{self.base_url}/rest/v1/order", headers=self.headers, params=params)
            resp.raise_for_status()
            orders = resp.json()
            
            # 데이터 구조 변환
            formatted_orders = []
            for order in orders:
                try:
                    # 회사 정보 추출
                    company_info = order.get("company", {})
                    company_name = company_info.get("company_name", "N/A") if company_info else "N/A"
                    
                    formatted_order = {
                        "order_id": str(order.get("order_id", "N/A")),
                        "company_name": company_name,
                        "is_dine_in": order.get("is_dine_in", True),
                        "total_price": order.get("total_price", 0),
                        "created_at": order.get("created_at"),
                        "is_printed": order.get("is_printed", False),
                        "items": []
                    }
                    
                    # 주문 항목 처리
                    order_items = order.get("order_items", [])
                    for item in order_items:
                        menu_item_info = item.get("menu_item", {})
                        menu_name = menu_item_info.get("menu_name", "N/A") if menu_item_info else "N/A"
                        
                        menu_item = {
                            "name": menu_name,
                            "quantity": item.get("quantity", 1),
                            "price": item.get("item_price", 0),
                            "options": []
                        }
                        
                        # 옵션 처리
                        options = item.get("options", [])
                        for option in options:
                            option_item_info = option.get("option_item", {})
                            if option_item_info:
                                menu_item["options"].append({
                                    "name": option_item_info.get("option_item_name", "N/A"),
                                    "price": option_item_info.get("option_price", 0)
                                })
                        
                        formatted_order["items"].append(menu_item)
                    
                    formatted_orders.append(formatted_order)
                except Exception as e:
                    logger.exception("주문 데이터 변환 중 오류: %s", e)
                    continue
            
            return formatted_orders
            
        except Exception as e:
            logger.exception("주문 데이터 조회 오류: %s", e)
            # Supabase에도 에러 로깅
            error_logger = get_error_logger()
            if error_logger:
                error_logger.log_network_error(
                    url=f"{self.base_url}/rest/v1/order",
                    error=e,
                    method="GET"
                )
            return []

    def get_order_by_id(self, order_id: int) -> Optional[Dict[str, Any]]:
        """특정 주문 ID의 상세 정보를 가져옵니다."""
        try:
            params = {
                "select": "*",
                "order_id": f"eq.{order_id}",
            }
            resp = requests.get(f"{self.base_url}/rest/v1/order", headers=self.headers, params=params)
            resp.raise_for_status()
            data = resp.json()
            return data[0] if data else None
        except Exception as e:
            logger.exception("주문 상세 조회 오류: %s", e)
            # Supabase에도 에러 로깅
            error_logger = get_error_logger()
            if error_logger:
                error_logger.log_network_error(
                    url=f"{self.base_url}/rest/v1/order",
                    error=e,
                    method="GET"
                )
            return None

    def delete_order(self, order_id: int) -> bool:
        """특정 주문을 삭제합니다."""
        try:
            # 주문 항목 옵션 삭제
            resp = requests.delete(
                f"{self.base_url}/rest/v1/order_item_option",
                headers=self.headers,
                params={"order_item_id": f"in.(select order_item_id from order_item where order_id={order_id})"}
            )
            if not resp.ok:
                logger.warning(f"주문 항목 옵션 삭제 응답: {resp.status_code} - {resp.text}")
            
            # 주문 항목 삭제
            resp = requests.delete(
                f"{self.base_url}/rest/v1/order_item",
                headers=self.headers,
                params={"order_id": f"eq.{order_id}"}
            )
            if not resp.ok:
                logger.warning(f"주문 항목 삭제 응답: {resp.status_code} - {resp.text}")
            
            # 주문 삭제
            resp = requests.delete(
                f"{self.base_url}/rest/v1/order",
                headers=self.headers,
                params={"order_id": f"eq.{order_id}"}
            )
            resp.raise_for_status()
            
            logger.info(f"주문 {order_id} 삭제 성공")
            return True
            
        except Exception as e:
            logger.exception("주문 삭제 오류: %s", e)
            # Supabase에도 에러 로깅
            error_logger = get_error_logger()
            if error_logger:
                error_logger.log_network_error(
                    url=f"{self.base_url}/rest/v1/order",
                    error=e,
                    method="DELETE"
                )
            return False
