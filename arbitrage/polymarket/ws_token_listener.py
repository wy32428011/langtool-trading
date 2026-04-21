import json
import logging
import time
import sys
import os

# 确保项目根目录在 sys.path 中
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.append(project_root)

from arbitrage.polymarket.ws_client import PolyMarketWebsocketClient

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """
    手动指定 Token ID 列表并进行监听的脚本
    使用方法: python ws_token_listener.py token1 token2 ...
    或者直接修改脚本中的 tokens 列表
    """
    # 1. 获取要监听的 tokens
    tokens = []
    if len(sys.argv) > 1:
        # 从命令行参数获取
        tokens = sys.argv[1:]
        logger.info(f"Using tokens from command line: {tokens}")
    else:
        # 如果没有命令行参数，可以交互式输入或者在这里硬编码
        print("请输入要监听的 Token IDs (多个用空格或逗号分隔，直接回车退出):")
        input_str = input().strip()
        if not input_str:
            logger.info("No tokens provided. Exiting.")
            return
        
        # 兼容空格和逗号分隔
        tokens = [t.strip() for t in input_str.replace(",", " ").split() if t.strip()]
        logger.info(f"Using tokens from input: {tokens}")

    if not tokens:
        logger.warning("No tokens to subscribe. Exiting.")
        return

    # 2. 实例化客户端
    client = PolyMarketWebsocketClient()

    def on_message_callback(message):
        """处理接收到的消息"""
        # 这里可以根据需求定制，比如只打印特定字段
        try:
            # Polymarket 的消息通常是列表或单个对象
            print(f"[{time.strftime('%H:%M:%S')}] Received: {json.dumps(message)}")
        except Exception as e:
            logger.error(f"Error in callback: {e}")

    # 3. 注册订阅
    # 注意：subscribe 会在连接建立后（或重新连接后）通过 _resubscribe 发送负载
    # 我们直接使用 subscribe 方法，它会自动调用 start()
    logger.info(f"Starting listener for {len(tokens)} tokens...")
    client.subscribe(tokens, channel="Market", callback=on_message_callback)

    # 4. 保持主线程运行
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping listener...")
        client.stop()
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        client.stop()

if __name__ == "__main__":
    main()
