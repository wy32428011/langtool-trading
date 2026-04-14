import os
import sys
import json

# 将项目根目录添加到 python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from arbitrage.polymarket.client import PolyMarketClient
from config import settings

def test_auth():
    print("--- 验证 Polymarket 认证配置 ---")
    print(f"API Key: {settings.poly_api_key or '未设置'}")
    print(f"API Secret: {'已设置' if settings.poly_api_secret else '未设置'}")
    print(f"API Passphrase: {'已设置' if settings.poly_api_passphrase else '未设置'}")
    print(f"Private Key: {'已设置' if settings.poly_private_key else '未设置'}")

    client = PolyMarketClient()
    
    if not client.api_key and not client.private_key:
        print("\n[跳过测试] 未检测到 API Key 或 Private Key。")
        return

    # 如果有私钥，尝试获取 API Key (L1)
    if client.private_key:
        print("\n正在尝试 L1 认证 (通过私钥获取/创建 API Key)...")
        try:
            api_key_data = client.create_api_key_l1()
            print("成功！L1 认证通过。")
            print(json.dumps(api_key_data, indent=2))
        except Exception as e:
            print(f"L1 认证失败: {e}")
            if "ModuleNotFoundError" in str(e):
                print("请安装 eth-account 库: pip install eth-account")

    # 尝试获取订单记录（这通常需要认证）
    print("\n正在尝试调用带认证的接口 (get_trades)...")
    try:
        # 使用 SDK 后的调用方式
        trades = client.get_trades()
        print("成功！认证通过。")
        print(f"获取到 {len(trades)} 条成交记录。")
    except Exception as e:
        print(f"认证测试失败: {e}")

if __name__ == "__main__":
    test_auth()
