import logging
import sqlite3
import json
import os
from datetime import datetime, timedelta

# 환경 변수 로딩
def load_env():
    """환경 변수 파일 로딩"""
    env_file = "default.env"
    if os.path.exists(env_file):
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        os.environ[key] = value
            print(f"환경 변수 로딩 완료: {env_file}")
        except Exception as e:
            print(f"환경 변수 로딩 오류: {e}")
    else:
        print(f"환경 변수 파일 없음: {env_file}")

# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def check_auto_print_status():
    """자동출력 상태 진단"""
    print("=== 자동출력 진단 시작 ===")
    
    # 환경 변수 로딩
    load_env()
    
    # 1. 프린터 설정 확인
    print("\n1. 프린터 설정 확인:")
    try:
        from src.printer.manager import PrinterManager
        printer_manager = PrinterManager()
        auto_print_enabled = printer_manager.is_auto_print_enabled()
        auto_config = printer_manager.get_auto_print_config()
        
        print(f"  자동출력 활성화: {auto_print_enabled}")
        print(f"  자동출력 설정: {auto_config}")
        
        # 프린터 상태 확인
        printer_status = printer_manager.check_printer_status()
        print(f"  프린터 상태: {printer_status}")
        
    except Exception as e:
        print(f"  프린터 설정 확인 오류: {e}")
        import traceback
        print(f"  상세 오류: {traceback.format_exc()}")
    
    # 2. 데이터베이스 상태 확인
    print("\n2. 데이터베이스 상태 확인:")
    unprinted_count = 0
    try:
        db_path = 'orders.db'
        if not os.path.exists(db_path):
            print(f"  데이터베이스 파일 없음: {db_path}")
            return
            
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 테이블 존재 확인
        tables_query = "SELECT name FROM sqlite_master WHERE type='table'"
        tables = [row[0] for row in cursor.execute(tables_query).fetchall()]
        print(f"  존재하는 테이블: {tables}")
        
        if 'order' not in tables:
            print("  'order' 테이블이 존재하지 않습니다.")
            conn.close()
            return
        
        # 최근 주문 조회
        query = """
        SELECT o.order_id, o.company_id, o.is_printed, o.created_at
        FROM [order] o
        WHERE datetime(o.created_at) > datetime('now', '-2 hours')
        ORDER BY o.created_at DESC
        LIMIT 10
        """
        
        rows = cursor.execute(query).fetchall()
        print(f"  최근 2시간 주문: {len(rows)}개")
        
        for row in rows:
            is_printed = bool(row['is_printed'])
            if not is_printed:
                unprinted_count += 1
            
            print(f"    주문ID: {row['order_id']}, "
                  f"출력여부: {'출력됨' if is_printed else '미출력'}, "
                  f"생성시간: {row['created_at']}")
        
        print(f"  미출력 주문: {unprinted_count}개")
        
        conn.close()
        
    except Exception as e:
        print(f"  데이터베이스 확인 오류: {e}")
        import traceback
        print(f"  상세 오류: {traceback.format_exc()}")
    
    # 3. 자동출력 시뮬레이션
    print("\n3. 자동출력 시뮬레이션:")
    if unprinted_count > 0:
        print("  미출력 주문이 있으므로 자동출력이 시도되어야 합니다.")
        print("  실제 자동출력을 테스트하려면 main.py를 실행하고 로그를 확인하세요.")
    else:
        print("  현재 미출력 주문이 없습니다.")
    
    print("\n=== 진단 완료 ===")

if __name__ == "__main__":
    try:
        check_auto_print_status()
    except Exception as e:
        print(f"진단 중 오류 발생: {e}")
        import traceback
        print(f"상세 오류: {traceback.format_exc()}") 