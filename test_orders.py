#!/usr/bin/env python3
"""최근 주문 조회 테스트 스크립트"""

import os
import sys
sys.path.append('.')

def load_env():
    """환경 변수 로드"""
    with open('default.env') as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                os.environ[key] = value.strip('"')

def main():
    try:
        # 환경 변수 로드
        load_env()
        
        # Supabase 클라이언트 임포트 및 생성
        from src.supabase_client import SupabaseClient
        client = SupabaseClient()
        
        # 최근 주문 조회
        print("🔄 Supabase에서 최근 주문 조회 중...")
        orders = client.get_orders(10)
        
        print(f"\n✅ 총 {len(orders)}개의 주문을 찾았습니다.\n")
        print("=" * 60)
        print("📋 최근 주문 10개")
        print("=" * 60)
        
        for i, order in enumerate(orders, 1):
            print(f"\n[{i:2d}] 주문 ID: {order['order_id']}")
            print(f"     회사명: {order['company_name']}")
            print(f"     총 가격: {order['total_price']:,}원")
            print(f"     매장/포장: {'매장' if order['is_dine_in'] else '포장'}")
            print(f"     생성일시: {order['created_at']}")
            print(f"     프린트 상태: {'✅ 완료' if order['is_printed'] else '❌ 미완료'}")
            
            if order.get('items'):
                print(f"     주문 항목: {len(order['items'])}개")
                for j, item in enumerate(order['items'][:3], 1):  # 처음 3개만 표시
                    print(f"       {j}. {item['menu_name']} x{item['quantity']} ({item['item_price']:,}원)")
                if len(order['items']) > 3:
                    print(f"       ... 외 {len(order['items'])-3}개 항목")
            
            if i < len(orders):
                print("     " + "-" * 40)
        
        print("\n" + "=" * 60)
        print("✨ 조회 완료!")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 