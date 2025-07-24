import os
import logging
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import json
from functools import lru_cache
import threading
from dataclasses import dataclass, asdict

import requests
from PySide6.QtCore import QObject, Signal
from src.error_logger import get_error_logger

logger = logging.getLogger(__name__)

@dataclass
class OrderBasic:
    """주문 기본 정보"""
    order_id: int
    company_id: int
    company_name: str
    is_dine_in: bool
    total_price: int
    created_at: str
    is_printed: bool

@dataclass
class OrderItem:
    """주문 아이템 정보"""
    order_item_id: int
    order_id: int
    menu_item_id: int
    menu_name: str
    quantity: int
    item_price: int

@dataclass
class OrderOption:
    """주문 옵션 정보"""
    order_item_option_id: int
    order_item_id: int
    option_item_id: int
    option_item_name: str
    option_price: int
    quantity: int = 1
    total_price: int = 0

class QueryCache:
    """쿼리 결과 캐싱 클래스"""
    
    def __init__(self, default_ttl: int = 300):  # 5분 기본 TTL
        self.cache = {}
        self.cache_times = {}
        self.default_ttl = default_ttl
        self.lock = threading.RLock()
    
    def get(self, key: str, ttl: int = None) -> Optional[Any]:
        """캐시에서 값 조회"""
        with self.lock:
            if key not in self.cache:
                return None
            
            ttl = ttl or self.default_ttl
            cache_time = self.cache_times.get(key)
            if cache_time and datetime.now() - cache_time > timedelta(seconds=ttl):
                # TTL 만료
                del self.cache[key]
                del self.cache_times[key]
                return None
            
            return self.cache[key]
    
    def set(self, key: str, value: Any) -> None:
        """캐시에 값 저장"""
        with self.lock:
            self.cache[key] = value
            self.cache_times[key] = datetime.now()
    
    def clear(self, pattern: str = None) -> None:
        """캐시 클리어 (패턴 매칭 지원)"""
        with self.lock:
            if pattern is None:
                self.cache.clear()
                self.cache_times.clear()
            else:
                keys_to_remove = [k for k in self.cache.keys() if pattern in k]
                for key in keys_to_remove:
                    del self.cache[key]
                    if key in self.cache_times:
                        del self.cache_times[key]

class OptimizedSupabaseClient(QObject):
    """최적화된 Supabase 클라이언트"""

    # 시그널 정의
    orders_loaded = Signal(list)  # 주문 데이터 로딩 완료 시그널
    
    def __init__(self) -> None:
        super().__init__()
        project_id = os.getenv("SUPABASE_PROJECT_ID")
        self.base_url = os.getenv("SUPABASE_URL") or f"https://{project_id}.supabase.co"
        self.api_key = os.getenv("SUPABASE_API_KEY")
        self.headers = {
            "apikey": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
        }
        
        # 캐시 시스템 초기화
        self.cache = QueryCache()
        
        # 캐시 TTL 설정 (초)
        self.CACHE_TTL = {
            'orders_basic': 300,      # 5분
            'companies': 3600,        # 1시간
            'menu_items': 1800,       # 30분
            'order_items': 600,       # 10분
            'order_options': 600,     # 10분
        }

    def _make_request(self, endpoint: str, params: Dict = None, method: str = "GET") -> Optional[List[Dict]]:
        """공통 HTTP 요청 처리"""
        try:
            url = f"{self.base_url}/rest/v1/{endpoint}"
            
            if method == "GET":
                resp = requests.get(url, headers=self.headers, params=params, timeout=10)
            elif method == "DELETE":
                resp = requests.delete(url, headers=self.headers, params=params, timeout=10)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            resp.raise_for_status()
            return resp.json()
            
        except Exception as e:
            logger.exception(f"{endpoint} 요청 오류: %s", e)
            # Supabase에도 에러 로깅
            error_logger = get_error_logger()
            if error_logger:
                error_logger.log_network_error(
                    url=url,
                    error=e,
                    method=method
                )
            return None

    def get_companies(self) -> Dict[int, str]:
        """회사 정보 조회 (캐싱됨)"""
        cache_key = "companies_all"
        cached = self.cache.get(cache_key, self.CACHE_TTL['companies'])
        if cached:
            return cached
        
        params = {"select": "company_id,company_name"}
        data = self._make_request("company", params)
        
        if data:
            companies = {item['company_id']: item['company_name'] for item in data}
            self.cache.set(cache_key, companies)
            return companies
        
        return {}

    def get_menu_items(self, menu_item_ids: List[int]) -> Dict[int, str]:
        """메뉴 아이템 정보 조회 (캐싱됨)"""
        if not menu_item_ids:
            return {}
        
        cache_key = f"menu_items_{','.join(map(str, sorted(menu_item_ids)))}"
        cached = self.cache.get(cache_key, self.CACHE_TTL['menu_items'])
        if cached:
            return cached
        
        ids_str = ','.join(map(str, menu_item_ids))
        params = {
            "select": "menu_item_id,menu_name",
            "menu_item_id": f"in.({ids_str})"
        }
        data = self._make_request("menu_item", params)
        
        if data:
            menu_items = {item['menu_item_id']: item['menu_name'] for item in data}
            self.cache.set(cache_key, menu_items)
            return menu_items
        
        return {}

    def get_orders_basic(self, limit: int = 10, offset: int = 0, 
                        only_unprinted: bool = False) -> List[OrderBasic]:
        """주문 기본 정보 조회 (1단계)"""
        cache_key = f"orders_basic_{limit}_{offset}_{only_unprinted}"
        cached = self.cache.get(cache_key, self.CACHE_TTL['orders_basic'])
        if cached:
            return [OrderBasic(**item) for item in cached]
        
        params = {
            "select": "order_id,company_id,is_dine_in,total_price,created_at,is_printed",
            "order": "created_at.desc",
            "limit": str(limit),
            "offset": str(offset)
        }
        
        if only_unprinted:
            params["is_printed"] = "eq.false"
        
        data = self._make_request("order", params)
        if not data:
            return []
        
        # 회사 정보 조회
        companies = self.get_companies()
        
        orders = []
        for item in data:
            company_name = companies.get(item['company_id'], 'N/A')
            order = OrderBasic(
                order_id=item['order_id'],
                company_id=item['company_id'],
                company_name=company_name,
                is_dine_in=item['is_dine_in'],
                total_price=item['total_price'],
                created_at=item['created_at'],
                is_printed=item['is_printed']
            )
            orders.append(order)
        
        # 캐시 저장 (dataclass를 dict로 변환)
        cache_data = [asdict(order) for order in orders]
        self.cache.set(cache_key, cache_data)
        
        return orders

    def get_order_items(self, order_ids: List[int]) -> Dict[int, List[OrderItem]]:
        """주문 아이템 조회 (2단계)"""
        if not order_ids:
            return {}
        
        cache_key = f"order_items_{','.join(map(str, sorted(order_ids)))}"
        cached = self.cache.get(cache_key, self.CACHE_TTL['order_items'])
        if cached:
            # 캐시된 데이터를 OrderItem 객체로 변환
            result = {}
            for order_id, items in cached.items():
                result[int(order_id)] = [OrderItem(**item) for item in items]
            return result
        
        ids_str = ','.join(map(str, order_ids))
        params = {
            "select": "order_item_id,order_id,menu_item_id,quantity,item_price",
            "order_id": f"in.({ids_str})"
        }
        
        data = self._make_request("order_item", params)
        if not data:
            return {}
        
        # 메뉴 아이템 정보 조회
        menu_item_ids = list(set(item['menu_item_id'] for item in data))
        menu_items = self.get_menu_items(menu_item_ids)
        
        # 주문별로 그룹화
        order_items = {}
        for item in data:
            order_id = item['order_id']
            if order_id not in order_items:
                order_items[order_id] = []
            
            menu_name = menu_items.get(item['menu_item_id'], 'N/A')
            order_item = OrderItem(
                order_item_id=item['order_item_id'],
                order_id=order_id,
                menu_item_id=item['menu_item_id'],
                menu_name=menu_name,
                quantity=item['quantity'],
                item_price=item['item_price']
            )
            order_items[order_id].append(order_item)
        
        # 캐시 저장 (dataclass를 dict로 변환)
        cache_data = {}
        for order_id, items in order_items.items():
            cache_data[str(order_id)] = [asdict(item) for item in items]
        self.cache.set(cache_key, cache_data)
        
        return order_items

    def get_order_options(self, order_item_ids: List[int]) -> Dict[int, List[OrderOption]]:
        """주문 옵션 조회 (3단계)"""
        if not order_item_ids:
            return {}
        
        cache_key = f"order_options_{','.join(map(str, sorted(order_item_ids)))}"
        cached = self.cache.get(cache_key, self.CACHE_TTL['order_options'])
        if cached:
            # 캐시된 데이터를 OrderOption 객체로 변환
            result = {}
            for item_id, options in cached.items():
                result[int(item_id)] = [OrderOption(**opt) for opt in options]
            return result
        
        ids_str = ','.join(map(str, order_item_ids))
        params = {
            "select": """
                order_item_option_id,
                order_item_id,
                option_item_id,
                quantity,
                total_price,
                option_item!inner(option_item_name,option_price)
            """,
            "order_item_id": f"in.({ids_str})"
        }
        
        data = self._make_request("order_item_option", params)
        if not data:
            return {}
        
        # 주문 아이템별로 그룹화
        item_options = {}
        for item in data:
            order_item_id = item['order_item_id']
            if order_item_id not in item_options:
                item_options[order_item_id] = []
            
            option_info = item.get('option_item', {})
            option = OrderOption(
                order_item_option_id=item['order_item_option_id'],
                order_item_id=order_item_id,
                option_item_id=item['option_item_id'],
                option_item_name=option_info.get('option_item_name', 'N/A'),
                option_price=option_info.get('option_price', 0),
                quantity=item.get('quantity', 1),
                total_price=item.get('total_price', 0)
            )
            item_options[order_item_id].append(option)
        
        # 캐시 저장 (dataclass를 dict로 변환)
        cache_data = {}
        for item_id, options in item_options.items():
            cache_data[str(item_id)] = [asdict(opt) for opt in options]
        self.cache.set(cache_key, cache_data)
        
        return item_options

    def get_orders_optimized(self, limit: int = 10, offset: int = 0, 
                           load_details: bool = True) -> List[Dict[str, Any]]:
        """최적화된 주문 조회"""
        try:
            # 1단계: 주문 기본 정보 조회
            orders_basic = self.get_orders_basic(limit, offset)
            if not orders_basic:
                return []
            
            if not load_details:
                # 기본 정보만 필요한 경우
                return [asdict(order) for order in orders_basic]
            
            # 2단계: 주문 아이템 조회
            order_ids = [order.order_id for order in orders_basic]
            order_items_dict = self.get_order_items(order_ids)
            
            # 3단계: 옵션 정보 조회 (필요한 경우만)
            all_order_item_ids = []
            for items in order_items_dict.values():
                all_order_item_ids.extend([item.order_item_id for item in items])
            
            order_options_dict = {}
            if all_order_item_ids:
                order_options_dict = self.get_order_options(all_order_item_ids)
            
            # 4단계: 데이터 조합
            formatted_orders = []
            for order_basic in orders_basic:
                order_items = order_items_dict.get(order_basic.order_id, [])
                
                formatted_items = []
                for item in order_items:
                    item_options = order_options_dict.get(item.order_item_id, [])
                    
                    formatted_item = {
                        "order_item_id": item.order_item_id,
                        "name": item.menu_name,
                        "quantity": item.quantity,
                        "price": item.item_price,
                        "options": [
                            {
                                "name": opt.option_item_name,
                                "price": opt.option_price,
                                "quantity": opt.quantity,
                                "total_price": opt.total_price
                            }
                            for opt in item_options
                        ]
                    }
                    formatted_items.append(formatted_item)
                
                formatted_order = {
                    "order_id": str(order_basic.order_id),
                    "company_name": order_basic.company_name,
                    "is_dine_in": order_basic.is_dine_in,
                    "total_price": order_basic.total_price,
                    "created_at": order_basic.created_at,
                    "is_printed": order_basic.is_printed,
                    "items": formatted_items
                }
                formatted_orders.append(formatted_order)
            
            return formatted_orders
            
        except Exception as e:
            logger.exception("최적화된 주문 조회 오류: %s", e)
            return []

    def get_orders(self, limit: int = 10) -> List[Dict[str, Any]]:
        """기존 인터페이스 호환성 유지"""
        return self.get_orders_optimized(limit=limit, load_details=True)

    def get_order_by_id(self, order_id: int) -> Optional[Dict[str, Any]]:
        """특정 주문 ID의 상세 정보 조회 (최적화됨)"""
        try:
            orders = self.get_orders_optimized(limit=1, offset=0)
            # 캐시에서 찾거나 직접 조회
            for order in orders:
                if int(order['order_id']) == order_id:
                    return order
            
            # 캐시에 없으면 직접 조회
            orders_basic = self.get_orders_basic(limit=100)  # 더 큰 범위에서 찾기
            for order_basic in orders_basic:
                if order_basic.order_id == order_id:
                    result = self.get_orders_optimized(limit=1, offset=0)
                    return result[0] if result else None
            
            return None
            
        except Exception as e:
            logger.exception("주문 상세 조회 오류: %s", e)
            return None

    def delete_order(self, order_id: int) -> bool:
        """주문 삭제 (캐시 무효화 포함)"""
        try:
            # 기존 삭제 로직
            success = self._delete_order_cascade(order_id)
            
            if success:
                # 관련 캐시 무효화
                self.cache.clear("orders_basic")
                self.cache.clear("order_items")
                self.cache.clear("order_options")
                logger.info(f"주문 {order_id} 삭제 및 캐시 무효화 완료")
            
            return success
            
        except Exception as e:
            logger.exception("주문 삭제 오류: %s", e)
            return False

    def _delete_order_cascade(self, order_id: int) -> bool:
        """주문 cascade 삭제"""
        try:
            # 1단계: 해당 주문의 order_item_id들을 먼저 조회
            order_items_data = self._make_request(
                "order_item", 
                {"select": "order_item_id", "order_id": f"eq.{order_id}"}
            )
            
            if order_items_data:
                order_item_ids = [str(item["order_item_id"]) for item in order_items_data]
                
                # 2단계: 조회된 order_item_id들로 order_item_option 삭제
                if order_item_ids:
                    order_item_ids_str = ",".join(order_item_ids)
                    params = {"order_item_id": f"in.({order_item_ids_str})"}
                    self._make_request("order_item_option", params, method="DELETE")
            
            # 3단계: 주문 항목 삭제
            params = {"order_id": f"eq.{order_id}"}
            self._make_request("order_item", params, method="DELETE")
            
            # 4단계: 주문 삭제
            data = self._make_request("order", params, method="DELETE")
            
            return data is not None
            
        except Exception as e:
            logger.exception("Cascade 삭제 오류: %s", e)
            return False

    def clear_cache(self, pattern: str = None) -> None:
        """캐시 수동 클리어"""
        self.cache.clear(pattern)
        logger.info(f"캐시 클리어 완료: {pattern or 'all'}")

    def get_cache_stats(self) -> Dict[str, Any]:
        """캐시 통계 정보"""
        with self.cache.lock:
            return {
                "total_keys": len(self.cache.cache),
                "cache_size_mb": len(str(self.cache.cache)) / (1024 * 1024),
                "oldest_entry": min(self.cache.cache_times.values()) if self.cache.cache_times else None,
                "newest_entry": max(self.cache.cache_times.values()) if self.cache.cache_times else None,
            }