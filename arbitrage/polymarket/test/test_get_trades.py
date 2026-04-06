import sys
import os
import json

# 将项目根目录添加到 python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from arbitrage.polymarket.client import PolyMarketClient

def test_get_trades():
    client = PolyMarketClient()
    
    print("--- 正在获取最近的 5 条成交记录 ---")
    try:
        trades = client.get_trades(limit=5)
        print(f"成功获取到 {len(trades)} 条记录。")
        for i, trade in enumerate(trades):
            print(f"\n成交 #{i+1}:")
            print(f"  Price: {trade.get('price')}")
            print(f"  Size: {trade.get('size')}")
            print(f"  Side: {trade.get('side')}")
            print(f"  Timestamp: {trade.get('timestamp')}")
            print(f"  Asset ID: {trade.get('asset_id')}")
    except Exception as e:
        print(f"获取成交记录失败: {e}")

    # 尝试按特定的资产 (Asset ID) 获取
    print("\n--- 正在尝试获取特定资产 (Asset ID) 的成交记录 ---")
    try:
        # 获取一个活跃市场
        markets = client.get_markets(limit=1, active=True)
        if markets:
            market = markets[0]
            token_ids = json.loads(market.get('clobTokenIds', '[]'))
            if token_ids:
                target_token = token_ids[0]
                print(f"市场问题: {market.get('question')}")
                print(f"正在查询 Asset ID: {target_token}")
                
                asset_trades = client.get_trades(asset_id=target_token, limit=3)
                print(f"该资产获取到 {len(asset_trades)} 条记录。")
                if asset_trades:
                    print(f"  第一条价格: {asset_trades[0].get('price')}")
            else:
                print("该市场没有找到 Token ID。")
    except Exception as e:
        print(f"按资产 ID 查询失败: {e}")

if __name__ == "__main__":
    test_get_trades()
