import os
import sqlite3
from contextlib import suppress
from pathlib import Path
from typing import Any, Dict, List, Optional
import requests
import logging
from src.error_logger import get_error_logger

SCHEMA_PATH = Path(__file__).parent / "sqlite_schema.sql"
DB_PATH = Path(os.getenv("CACHE_DB_PATH", "cache.db"))

logger = logging.getLogger(__name__)
# Supabase 테이블 이름을 명시적으로 나열하여 허용 리스트를 구성합니다.
VALID_TABLES = {
    "company",
    "menu_category",
    "menu_item",
    "menu_item_option_group",
    "option_group",
    "option_group_item",
    "option_item",
    "order",
    "order_item",
    "order_item_option",
}

class SupabaseCache:
    """SQLite에 Supabase 테이블을 캐싱합니다."""

    def __init__(self, db_path: Path = DB_PATH, supabase_config: Optional[Dict[str, str]] = None) -> None:
        self.db_path = Path(db_path)
        self.base_url = supabase_config.get('url') if supabase_config else None
        self.api_key = supabase_config.get('api_key') if supabase_config else None
        self.headers = {
            "apikey": self.api_key or "",
            "Authorization": f"Bearer {self.api_key}" if self.api_key else "",
        }

    # ------------------------------------------------------------------
    def setup_sqlite(self) -> None:
        """로컬 SQLite 데이터베이스와 테이블을 초기화합니다."""
        try:
            conn = sqlite3.connect(self.db_path)
            with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
                sql = f.read()
            
            # SQL 문장을 개별적으로 분리
            statements = [stmt.strip() for stmt in sql.split(';') if stmt.strip()]
            
            # 각 문장을 개별적으로 실행
            for stmt in statements:
                try:
                    conn.execute(stmt)
                    conn.commit()
                except sqlite3.Error as e:
                    logger.error(f"SQL 실행 오류: {e}\n문장: {stmt}")
            
            # cache_meta 테이블이 없으면 생성
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            conn.commit()
            
            # 기존 order 테이블에 새 컬럼들 추가 (마이그레이션)
            try:
                conn.execute("ALTER TABLE \"order\" ADD COLUMN print_status VARCHAR(20) DEFAULT '신규'")
                conn.commit()
                logger.info("print_status 컬럼이 추가되었습니다.")
            except sqlite3.Error:
                pass  # 이미 존재하는 경우
                
            try:
                conn.execute("ALTER TABLE \"order\" ADD COLUMN print_attempts INTEGER DEFAULT 0")
                conn.commit()
                logger.info("print_attempts 컬럼이 추가되었습니다.")
            except sqlite3.Error:
                pass  # 이미 존재하는 경우
                
            try:
                conn.execute("ALTER TABLE \"order\" ADD COLUMN last_print_attempt TIMESTAMP")
                conn.commit()
                logger.info("last_print_attempt 컬럼이 추가되었습니다.")
            except sqlite3.Error:
                pass  # 이미 존재하는 경우
                
            # order_item_option 테이블에 quantity 컬럼 추가 (마이그레이션)
            try:
                conn.execute("ALTER TABLE order_item_option ADD COLUMN quantity INTEGER DEFAULT 1")
                conn.commit()
                logger.info("order_item_option.quantity 컬럼이 추가되었습니다.")
            except sqlite3.Error:
                pass  # 이미 존재하는 경우
                
            # order_item_option 테이블에 total_price 컬럼 추가 (마이그레이션)
            try:
                conn.execute("ALTER TABLE order_item_option ADD COLUMN total_price INTEGER DEFAULT 0")
                conn.commit()
                logger.info("order_item_option.total_price 컬럼이 추가되었습니다.")
            except sqlite3.Error:
                pass  # 이미 존재하는 경우
            
        except Exception as e:
            logger.error(f"데이터베이스 초기화 오류: {e}")
            # Supabase에도 에러 로깅
            error_logger = get_error_logger()
            if error_logger:
                error_logger.log_database_error(
                    operation="database_initialization",
                    error=e,
                    table_name="sqlite_setup"
                )
        finally:
            conn.close()

    # ------------------------------------------------------------------
    def fetch_and_store_table(self, table_name: str) -> None:
        """Supabase에서 테이블을 가져와 SQLite에 저장합니다."""
        if not self.base_url:
            return
        if table_name not in VALID_TABLES:
            raise ValueError(f"Invalid table name: {table_name}")
        params = {"select": "*"}
        try:
            resp = requests.get(
                f"{self.base_url}/rest/v1/{table_name}",
                headers=self.headers,
                params=params,
                timeout=10,
            )
            resp.raise_for_status()
        except requests.Timeout:
            logger.error("Timeout while fetching table '%s'", table_name)
            # Supabase에도 에러 로깅
            error_logger = get_error_logger()
            if error_logger:
                error_logger.log_network_error(
                    url=f"{self.base_url}/rest/v1/{table_name}",
                    error=Exception(f"Timeout while fetching table '{table_name}'"),
                    method="GET"
                )
            return
        rows = resp.json()
        if not rows:
            return
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(f'DELETE FROM "{table_name}"')
        cols = list(rows[0].keys())
        placeholders = ",".join(["?"] * len(cols))
        quoted_cols = ",".join([f'"{c}"' for c in cols])
        insert_sql = f'INSERT INTO "{table_name}" ({quoted_cols}) VALUES ({placeholders})'
        for row in rows:
            values = [row.get(col) for col in cols]
            cursor.execute(insert_sql, values)
        conn.commit()
        conn.close()

    # ------------------------------------------------------------------
    def join_order_detail(self, order_id: int) -> Dict[str, Any]:
        """주문과 관련 테이블을 조인하여 상세 정보를 반환합니다."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        query = """
        SELECT o.order_id, o.is_dine_in, o.total_price, o.created_at, o.signature_data,
               o.print_status, o.print_attempts, o.last_print_attempt, o.is_printed,
               c.company_name, c.required_signature,
               oi.order_item_id, oi.quantity, oi.item_price,
               mi.menu_name,
               opt.option_item_name, opt.option_price, oio.quantity as option_quantity, oio.total_price as option_total_price
        FROM "order" o
        JOIN company c ON c.company_id = o.company_id
        LEFT JOIN order_item oi ON oi.order_id = o.order_id
        LEFT JOIN menu_item mi ON mi.menu_item_id = oi.menu_item_id
        LEFT JOIN order_item_option oio ON oio.order_item_id = oi.order_item_id
        LEFT JOIN option_item opt ON opt.option_item_id = oio.option_item_id
        WHERE o.order_id = ?
        ORDER BY oi.order_item_id
        """
        rows = cursor.execute(query, (order_id,)).fetchall()
        conn.close()
        if not rows:
            return {}
        order: Dict[str, Any] = {
            "order_id": rows[0]["order_id"],
            "company_name": rows[0]["company_name"],
            "required_signature": bool(rows[0]["required_signature"]),
            "is_dine_in": bool(rows[0]["is_dine_in"]),
            "total_price": rows[0]["total_price"],
            "created_at": rows[0]["created_at"],
            "signature_data": rows[0]["signature_data"],
            "is_printed": bool(rows[0]["is_printed"]),
            "print_status": rows[0]["print_status"],
            "print_attempts": rows[0]["print_attempts"] or 0,
            "last_print_attempt": rows[0]["last_print_attempt"],
            "items": [],
        }
        item_map: Dict[int, Dict[str, Any]] = {}
        for row in rows:
            item_id = row["order_item_id"]
            if item_id not in item_map:
                item_map[item_id] = {
                    "name": row["menu_name"],
                    "quantity": row["quantity"],
                    "price": row["item_price"],
                    "options": [],
                }
            if row["option_item_name"]:
                item_map[item_id]["options"].append(
                    {
                        "name": row["option_item_name"], 
                        "price": row["option_price"],
                        "quantity": row["option_quantity"] or 1,
                        "total_price": row["option_total_price"] or 0
                    }
                )
        order["items"] = list(item_map.values())
        return order

    # ------------------------------------------------------------------
    def get_recent_orders(self, limit: int = 50) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        query = """
        SELECT o.order_id, o.company_id, o.is_dine_in, o.total_price, o.created_at, o.signature_data,
               o.is_printed, o.print_status, o.print_attempts, o.last_print_attempt,
               c.company_name, c.required_signature
        FROM "order" o
        JOIN company c ON c.company_id = o.company_id
        ORDER BY o.created_at DESC
        LIMIT ?
        """
        rows = cursor.execute(query, (limit,)).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_table_data(self, table_name: str) -> List[Dict[str, Any]]:
        """테이블의 모든 데이터를 가져옵니다."""
        if table_name not in VALID_TABLES:
            raise ValueError(f"Invalid table name: {table_name}")
            
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            cursor.execute(f'SELECT * FROM "{table_name}"')
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def delete_order_from_cache(self, order_id: int) -> bool:
        """로컬 캐시에서 주문을 삭제합니다."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 주문 항목 옵션 삭제
            cursor.execute("""
                DELETE FROM order_item_option 
                WHERE order_item_id IN (
                    SELECT order_item_id FROM order_item WHERE order_id = ?
                )
            """, (order_id,))
            
            # 주문 항목 삭제
            cursor.execute('DELETE FROM order_item WHERE order_id = ?', (order_id,))
            
            # 주문 삭제
            cursor.execute('DELETE FROM "order" WHERE order_id = ?', (order_id,))
            
            conn.commit()
            conn.close()
            
            logger.info(f"로컬 캐시에서 주문 {order_id} 삭제 성공")
            return True
            
        except Exception as e:
            logger.error(f"로컬 캐시에서 주문 삭제 오류: {e}")
            # Supabase에도 에러 로깅
            error_logger = get_error_logger()
            if error_logger:
                error_logger.log_database_error(
                    operation="delete_order",
                    error=e,
                    table_name="order",
                    order_id=str(order_id)
                )
            return False
