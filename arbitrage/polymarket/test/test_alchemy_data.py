import sys
import os
import json

# 将项目根目录添加到 python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from arbitrage.polymarket.alchemy_client import AlchemyClient

def test_fetch_token_data():
    """
    使用 Alchemy API 获取合约地址 0x4D97DCd97eC945f40cF65F87097ACe5EA0476045 的数据
    """
    # 如果没有配置 API KEY，这里会报错，所以我们手动检查下
    from config import settings
    if not settings.alchemy_api_key:
        print("警告: settings.alchemy_api_key 未设置。请在环境变量或 config.py 中配置。")
        # 如果是 Junie 调试，可能需要临时设置一个以观察效果（假设用户希望看到代码逻辑）
        # return

    # 初始化客户端 (Polymarket 在 Polygon 网络)
    client = AlchemyClient()
    
    contract_address = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
    print(f"--- 正在获取合约地址数据: {contract_address} ---")
    
    try:
        # 1. 获取代币元数据
        metadata = client.get_token_metadata(contract_address)
        print("\n1. 代币元数据 (Alchemy Token Metadata):")
        print(json.dumps(metadata, indent=4))
        
        # 2. 调用通用的 ERC20 查询 (例如 totalSupply)
        # ERC20 totalSupply() signature is 0x18160ddd
        total_supply_payload = {
            "id": 1,
            "jsonrpc": "2.0",
            "method": "eth_call",
            "params": [
                {
                    "to": contract_address,
                    "data": "0x18160ddd" 
                },
                "latest"
            ]
        }
        # 也可以直接用 client.call_rpc_method
        total_supply_resp = client.call_rpc_method("eth_call", [
                {
                    "to": contract_address,
                    "data": "0x18160ddd" 
                },
                "latest"
            ])
        
        print("\n2. 合约 totalSupply (16进制):")
        print(json.dumps(total_supply_resp, indent=4))
        
        # 3. 获取资产转移记录 (最近几条)
        # Polymarket 这种条件代币交易非常频繁
        print("\n3. 最近的代币转移记录 (Asset Transfers):")
        transfers = client.get_asset_transfers(
            contract_addresses=[contract_address],
            category=["erc20"],
            from_block="0x3B60000" # 给一个较大的起始区块号，防止数据太多或太旧
        )
        # 打印前几条转移记录
        results = transfers.get("result", {}).get("transfers", [])
        print(f"获取到 {len(results)} 条转移记录。前 2 条示例：")
        for i, t in enumerate(results[:2]):
            print(f"  [{i}] From: {t.get('from')} -> To: {t.get('to')}, Value: {t.get('value')} {t.get('asset')}")

    except Exception as e:
        print(f"获取数据失败: {str(e)}")
        if "401" in str(e) or "403" in str(e):
            print("错误详情: API Key 可能无效或网络连接被拒绝。")

if __name__ == "__main__":
    test_fetch_token_data()
