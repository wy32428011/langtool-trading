import sys
import os
import json
from datetime import datetime

# 将项目根目录添加到 python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from arbitrage.polymarket.client import PolyMarketClient
from arbitrage.polymarket.alchemy_client import AlchemyClient

def test_fetch_user_transactions(wallet_address=None):
    """
    测试通过钱包地址获取交易数据
    """
    # 1. 初始化客户端
    poly_client = PolyMarketClient()
    alchemy_client = AlchemyClient()
    
    # 如果未指定，则使用当前配置的钱包地址
    if not wallet_address:
        wallet_address = poly_client.clob_client.get_address()
    
    print(f"--- 正在查询钱包地址的数据: {wallet_address} ---")
    
    # A. 获取 Polymarket CLOB 成交记录 (Off-chain matching)
    print("\n[A] 获取 Polymarket CLOB 成交记录 (Trades):")
    try:
        trades = poly_client.get_trades(maker_address=wallet_address, limit=5)
        print(f"获取到 {len(trades)} 条成交记录。")
        for i, trade in enumerate(trades):
            print(f"  [{i}] ID: {trade.get('id')}, Market: {trade.get('market')}, Price: {trade.get('price')}, Size: {trade.get('size')}, Side: {trade.get('side')}")
    except Exception as e:
        print(f"获取 CLOB 成交记录失败: {str(e)}")

    # B. 获取 Polymarket 链上资产转移 (On-chain ERC20)
    print("\n[B] 获取链上资产转移 (Asset Transfers):")
    try:
        # 我们主要关注 USDC 和条件代币的转移
        USDC_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
        CTF_ADDRESS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
        
        # 1. 查询作为发送者的转移 (Outbound)
        print(f"查询 {wallet_address} 的转出记录...")
        transfers_from = alchemy_client.get_asset_transfers(
            from_address=wallet_address,
            contract_addresses=[USDC_ADDRESS, CTF_ADDRESS],
            category=["erc20"]
        )
        txs_out = transfers_from.get("transfers", [])
        print(f"获取到 {len(txs_out)} 条转出记录。")
        for i, tx in enumerate(txs_out[:3]):
            print(f"  [{i}] To: {tx.get('to')}, Value: {tx.get('value')} {tx.get('asset')}, Hash: {tx.get('hash')}")
            
        # 2. 查询作为接收者的转移 (Inbound)
        print(f"\n查询 {wallet_address} 的转入记录...")
        transfers_to = alchemy_client.get_asset_transfers(
            to_address=wallet_address,
            contract_addresses=[USDC_ADDRESS, CTF_ADDRESS],
            category=["erc20"]
        )
        txs_in = transfers_to.get("transfers", [])
        print(f"获取到 {len(txs_in)} 条转入记录。")
        for i, tx in enumerate(txs_in[:3]):
            print(f"  [{i}] From: {tx.get('from')}, Value: {tx.get('value')} {tx.get('asset')}, Hash: {tx.get('hash')}")
            
    except Exception as e:
        print(f"获取链上资产转移失败: {str(e)}")

if __name__ == "__main__":
    # 可以通过命令行参数传入地址，默认使用配置的地址
    target_address = sys.argv[1] if len(sys.argv) > 1 else None
    test_fetch_user_transactions(target_address)
