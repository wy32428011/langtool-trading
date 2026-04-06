import json
from arbitrage.polymarket.client import PolyMarketClient
from typing import Dict, Any

def print_json(data: Any, title: str):
    print(f"\n{'='*20} {title} {'='*20}")
    if isinstance(data, (dict, list)):
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(data)

def test_all_interfaces():
    # 可以在这里设置代理，如果需要的话
    proxies = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}
    client = PolyMarketClient()
    
    test_token_id = None
    test_market_id = None

    # 1. 测试 get_markets
    print("正在测试 get_markets...")
    try:
        markets = client.get_markets(limit=10, active=True)
        print_json(markets[:2], "get_markets Output (Showing first 2 of 10)")
        for m in markets:
            clob_token_ids_str = m.get('clobTokenIds')
            if clob_token_ids_str:
                try:
                    clob_token_ids = json.loads(clob_token_ids_str)
                    if clob_token_ids:
                        test_token_id = clob_token_ids[0]
                        test_market_id = m.get('id')
                        print(f"找到活跃市场的 Token ID: {test_token_id}, Market ID: {test_market_id}")
                        break
                except:
                    continue
    except Exception as e:
        print(f"get_markets 失败: {e}")

    # 2. 测试 get_market_by_id
    if test_market_id:
        print(f"\n正在测试 get_market_by_id (ID: {test_market_id})...")
        try:
            market_detail = client.get_market_by_id(test_market_id)
            print_json(market_detail, "get_market_by_id Output")
        except Exception as e:
            print(f"get_market_by_id 失败: {e}")
    else:
        print("\n跳过 get_market_by_id: 没有可用的市场 ID")

    # 如果没找到 token_id，用一个常用的 (Donald Trump 2024? 实际上这里应该用一个更稳妥的)
    if not test_token_id:
        # 这是一个示例 Token ID (Trump to win 2024 - 虽然已经过去了，但可能还有历史数据或类似 ID)
        # 更好的办法是找一个当前活跃的。
        # 我们可以尝试一个已知的稳定 token_id 或者让用户通过 get_markets 的结果手动填入
        test_token_id = "21742410317351651817109249764506828570371457497262070381534003050417631165565"
    
    # 强制尝试一个可能有效的 Token ID (例如：'Will Bitcoin hit $100k in 2025?' 的某个 outcome)
    # 如果上面的自动获取失败了，这里至少提供一个结构参考

    # 3. 测试 get_orderbook
    print(f"\n正在测试 get_orderbook (Token: {test_token_id})...")
    try:
        orderbook = client.get_orderbook(test_token_id)
        print_json(orderbook, "get_orderbook Output")
    except Exception as e:
        print(f"get_orderbook 失败: {e}")

    # 4. 测试 get_price_history
    print(f"\n正在测试 get_price_history (Token: {test_token_id})...")
    try:
        history_data = client.get_price_history(test_token_id)
        history = history_data.get("history", [])
        print_json(history[:5], "get_price_history Output (First 5)")
    except Exception as e:
        print(f"get_price_history 失败: {e}")

    # 5. 测试 get_midpoint_price
    print(f"\n正在测试 get_midpoint_price (Token: {test_token_id})...")
    try:
        price = client.get_midpoint_price(test_token_id)
        print(f"Midpoint Price: {price}")
    except Exception as e:
        print(f"get_midpoint_price 失败: {e}")

    # 6. 测试 get_events
    print("\n正在测试 get_events...")
    test_event_id = None
    try:
        events = client.get_events(limit=5, active=True)
        print_json(events[:2], "get_events Output (First 2)")
        if events:
            test_event_id = events[0].get("id")
    except Exception as e:
        print(f"get_events 失败: {e}")

    # 7. 测试 get_event_by_id
    if test_event_id:
        print(f"\n正在测试 get_event_by_id (ID: {test_event_id})...")
        try:
            event_detail = client.get_event_by_id(test_event_id)
            print_json(event_detail, "get_event_by_id Output")
        except Exception as e:
            print(f"get_event_by_id 失败: {e}")

if __name__ == "__main__":
    test_all_interfaces()
