import sys
import os
import json

# 将项目根目录添加到 python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from arbitrage.polymarket.alchemy_client import AlchemyClient

# 核心合约地址 (Conditional Tokens)
CORE_CONTRACT = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"

# 事件 Topic 签名
TOPICS = {
    "PositionSplit": "0x1e617d36371752b1156828593e3e00115003c27632644268e378c858548c26f7",
    "PositionsMerge": "0xc7001ca2f4a4753066607a7593c6f1a80809b4f0b240e1b203c9142e01314902"
}

def test_fetch_events_by_condition_id(condition_id: str):
    client = AlchemyClient()
    if not client.api_key:
        print("警告: Alchemy API Key 未正确配置。")
        return

    print(f"--- 正在查询 Condition ID: {condition_id} ---")
    
    # 获取最新区块，向上回溯
    try:
        latest_block_resp = client.call_rpc_method("eth_blockNumber", [])
        latest_block = int(latest_block_resp.get("result", "0x0"), 16)
        # 免费版限制 10 个区块，我们尝试查最近的 10 个区块
        from_block = hex(latest_block - 9)
        to_block = hex(latest_block)
        print(f"当前最新区块: {latest_block}, 查询范围: [{from_block}, {to_block}]")
    except Exception as e:
        print(f"获取最新区块失败: {e}")
        from_block = "latest"
        to_block = "latest"

    # 在 eth_getLogs 中，topics[0] 是事件哈希，topics[1] 是第一个 indexed 参数
    # PositionSplit(address indexed stakeholder, address indexed collateralToken, bytes32 indexed conditionId, ...)
    # 注意：在 ConditionalTokens 合约中，PositionSplit 的参数顺序可能不同，需要确认。
    # 通常 conditionId 是作为 indexed 参数的。
    
    for event_name, topic0 in TOPICS.items():
        print(f"\n查询事件: {event_name}")
        for pos in range(1, 4):
            print(f"尝试将 conditionId 放在 topics[{pos}]")
            topics = [topic0] + [None] * (pos - 1) + [condition_id]
            try:
                logs_resp = client.get_logs(
                    address=CORE_CONTRACT,
                    from_block=from_block,
                    to_block=to_block,
                    topics=topics
                )
                logs = logs_resp.get("result", [])
                if logs:
                    print(f"在 topics[{pos}] 找到 {len(logs)} 条记录！")
                    break
                else:
                    print("未找到。")
            except Exception as e:
                print(f"查询失败: {e}")

if __name__ == "__main__":
    # 使用较新的 conditionId
    test_id = "0x064d33e3f5703792aafa92bfb0ee10e08f461b1b34c02c1f02671892ede1609a"
    test_fetch_events_by_condition_id(test_id)
