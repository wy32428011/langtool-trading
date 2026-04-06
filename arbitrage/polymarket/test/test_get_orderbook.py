import json
import os
import sys

# 将项目根目录添加到 pythonpath
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from arbitrage.polymarket.client import PolyMarketClient

def test_get_orderbook():
    print("--- 测试获取订单簿 ---")
    client = PolyMarketClient()
    
    # 1. 获取一个活跃市场
    print("获取活跃市场...")
    markets = client.get_markets(limit=1, active=True)
    if not markets:
        print("未找到活跃市场。")
        return
    
    market = markets[0]
    question = market.get('question')
    market_id = market.get('id')
    print(f"市场: {question}")
    
    # 2. 获取 Token ID
    clob_token_ids_str = market.get('clobTokenIds')
    if not clob_token_ids_str:
        print("市场没有 clobTokenIds。")
        return
        
    token_ids = json.loads(clob_token_ids_str)
    if not token_ids:
        print("Token ID 列表为空。")
        return
        
    token_id = token_ids[0]
    print(f"正在获取 Token ID {token_id} 的订单簿...")
    
    # 3. 获取订单簿
    try:
        orderbook = client.get_orderbook(token_id)
        # orderbook 通常是字典，包含 'bids', 'asks', 'hash', 'timestamp' 等
        print(f"获取订单簿成功！")
        
        # 打印部分结果
        bids = getattr(orderbook, 'bids', []) if not isinstance(orderbook, dict) else orderbook.get('bids', [])
        asks = getattr(orderbook, 'asks', []) if not isinstance(orderbook, dict) else orderbook.get('asks', [])
        
        print(f"买单数量: {len(bids)}")
        print(f"卖单数量: {len(asks)}")
        
        if bids:
            print(f"最高买价: {bids[0].price if hasattr(bids[0], 'price') else bids[0].get('price')}")
        if asks:
            print(f"最低卖价: {asks[0].price if hasattr(asks[0], 'price') else asks[0].get('price')}")
            
    except Exception as e:
        print(f"获取单笔订单簿失败: {e}")

    # 4. 测试批量获取订单簿
    if len(token_ids) > 1:
        print(f"\n正在批量获取 {len(token_ids)} 个 Token 的订单簿...")
        try:
            books = client.get_orderbooks(token_ids)
            print(f"批量获取成功，共 {len(books)} 条记录。")
        except Exception as e:
            print(f"批量获取失败: {e}")

if __name__ == "__main__":
    test_get_orderbook()
