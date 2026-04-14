import sys
import os
import json
import time

# 将项目根目录添加到 python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from arbitrage.polymarket.alchemy_client import AlchemyClient

# 核心合约地址 (Polymarket Conditional Tokens / Market Maker)
CORE_CONTRACT = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"

# 事件 Topic 签名 (keccak256)
TOPICS = {
    "OrderFilled": "0x1d2119cf186a8a37cfc2111100522c0703f8319f688086915f7d29831a2f6430",
    "PositionSplit": "0x1e617d36371752b1156828593e3e00115003c27632644268e378c858548c26f7",
    "PositionsMerge": "0xc7001ca2f4a4753066607a7593c6f1a80809b4f0b240e1b203c9142e01314902"
}

def test_fetch_polymarket_events():
    client = AlchemyClient()
    if not client.api_key: # 这是一个占位符，如果未配置会报错
        print("警告: Alchemy API Key 未正确配置。请在 .env 中设置 ALCHEMY_API_KEY。")
        # return

    print(f"--- 正在从核心合约获取事件: {CORE_CONTRACT} ---")
    
    # 我们获取最近 10 个区块的日志，或者指定一个起始区块
    # 获取当前最新区块
    try:
        latest_block_resp = client.call_rpc_method("eth_blockNumber", [])
        latest_block = int(latest_block_resp.get("result", "0x0"), 16)
        # 免费版限制区块范围为 10 个区块（实际上是 10 个区块以内，即 end - start < 10）
        # 如果 latest_block = 100, [91, 100] 是 10 个区块 (91,92,93,94,95,96,97,98,99,100)
        from_block = hex(latest_block - 9)
        to_block = hex(latest_block)
        print(f"当前最新区块: {latest_block}, 查询范围: [{from_block}, {to_block}]")
    except Exception as e:
        print(f"获取最新区块失败: {e}")
        from_block = "latest"
        to_block = "latest"

    for event_name, topic0 in TOPICS.items():
        print(f"\n正在查询事件: {event_name} ({topic0})")
        try:
            logs_resp = client.get_logs(
                address=CORE_CONTRACT,
                from_block=from_block,
                to_block=to_block,
                topics=[topic0]
            )
            logs = logs_resp.get("result", [])
            print(f"找到 {len(logs)} 条 {event_name} 记录。")
            
            if logs:
                # 打印第一条作为示例
                example = logs[0]
                print(f"示例日志 (Block: {int(example.get('blockNumber', '0x0'), 16)}):")
                # print(json.dumps(example, indent=2))
                print(f"  Transaction Hash: {example.get('transactionHash')}")
                print(f"  Data: {example.get('data')[:66]}...") # 截断数据部分
        except Exception as e:
            print(f"查询 {event_name} 失败: {e}")

if __name__ == "__main__":
    test_fetch_polymarket_events()
