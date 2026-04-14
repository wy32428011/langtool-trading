import json
import logging
import websocket
import threading
import time
from typing import List, Callable, Optional
from config import settings

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PolyMarketWebsocketClient:
    """
    Polymarket WebSocket 客户端，用于实时获取订单簿和交易数据。
    参考: https://docs.polymarket.com/api-reference/wss/market
    """
    
    WSS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

    def __init__(self):
        self.ws = None
        self.subscriptions = {} # channel -> {assets: set, callback: func}
        self.is_running = False
        self.thread = None
        self.should_reconnect = True
        self.reconnect_delay = 1 # 初始重连延迟（秒）
        self.max_reconnect_delay = 60 # 最大重连延迟（秒）

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)

            # Polymarket 返回 JSON 数组，每个元素是一条事件
            items = data if isinstance(data, list) else [data]

            for item in items:
                if item.get("event") == "subscription_succeeded":
                    logger.info(f"Subscription confirmed: {item}")
                    continue

                for channel, sub in self.subscriptions.items():
                    if sub.get("callback"):
                        sub["callback"](item)

        except Exception as e:
            logger.error(f"Error parsing websocket message: {e}")

    def _on_error(self, ws, error):
        logger.error(f"Websocket error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        logger.info(f"Websocket connection closed: {close_status_code} - {close_msg}")
        self.is_running = False
        if self.should_reconnect:
            logger.info(f"Attempting to reconnect in {self.reconnect_delay} seconds...")
            threading.Timer(self.reconnect_delay, self.start).start()
            # 指数退避
            self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)

    def _on_open(self, ws):
        logger.info("Websocket connection opened.")
        self.is_running = True
        self.reconnect_delay = 1 # 重置重连延迟
        # 连接打开后重新订阅
        self._resubscribe()

    def _resubscribe(self):
        """连接恢复后重新发送所有订阅请求"""
        if not self.subscriptions:
            return
        
        logger.info(f"Resubscribing to {len(self.subscriptions)} channels...")
        for channel, sub in self.subscriptions.items():
            assets = list(sub.get("assets", []))
            if assets:
                self._send_subscribe_payload(assets, channel)

    def start(self):
        """
        启动 WebSocket 客户端线程
        """
        # 如果已经运行且连接正常，不重复启动
        if self.is_running and self.ws and self.ws.sock and self.ws.sock.connected:
            return
        
        self.should_reconnect = True
        self.ws = websocket.WebSocketApp(
            self.WSS_URL,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close
        )
        
        # 使用 run_forever，并设置 ping 间隔以维持连接
        run_kwargs = {
            "ping_interval": 20,
            "ping_timeout": 10,
        }
        
        # 只有在配置了代理主机时才应用代理设置
        if settings.proxy_host:
            run_kwargs.update({
                "http_proxy_host": settings.proxy_host,
                "http_proxy_port": settings.proxy_port,
                "proxy_type": "http",
            })
            logger.info(f"Using proxy: {settings.proxy_host}:{settings.proxy_port}")

        self.thread = threading.Thread(
            target=self.ws.run_forever,
            kwargs=run_kwargs
        )
        self.thread.daemon = True
        self.thread.start()
        
        # 等待连接建立（非阻塞，订阅会自动在 on_open 后触发）
        # 但如果是同步调用 subscribe，需要确保连接建立

    def stop(self):
        """
        停止 WebSocket 客户端
        """
        self.should_reconnect = False
        if self.ws:
            self.ws.close()
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=1)

    def _send_subscribe_payload(self, assets_ids: List[str], channel: str):
        """发送订阅协议负载"""
        if not self.ws or not self.ws.sock or not self.ws.sock.connected:
            logger.error(f"Cannot send subscription: connection is not ready.")
            return False
            
        payload = {
            "assets_ids": assets_ids,
            "type": channel   # Polymarket 协议：type 即频道名，如 "Market"、"Trade"
        }
        try:
            self.ws.send(json.dumps(payload))
            logger.info(f"Sent subscription request for {channel} with assets: {assets_ids}")
            return True
        except Exception as e:
            logger.error(f"Failed to send subscription: {e}")
            return False

    def subscribe(self, assets_ids: List[str], channel: str = "Market", callback: Optional[Callable] = None):
        """
        订阅特定资产的频道
        
        :param assets_ids: 资产 ID 列表 (Token IDs)
        :param channel: 频道名称，例如 "book", "trades"
        :param callback: 收到消息时的回调函数
        """
        # 记录订阅信息，用于重连
        if channel not in self.subscriptions:
            self.subscriptions[channel] = {"assets": set(), "callback": callback}
        
        self.subscriptions[channel]["assets"].update(assets_ids)
        if callback:
            self.subscriptions[channel]["callback"] = callback

        # 如果未运行则启动
        if not self.is_running:
            self.start()
            # 这种情况下，订阅会在 on_open 触发时通过 _resubscribe 完成
        else:
            # 如果已经在运行，尝试直接发送
            # 增加一点点延迟确保 sock 已准备好（如果刚刚 open）
            if self.ws and self.ws.sock and self.ws.sock.connected:
                self._send_subscribe_payload(assets_ids, channel)
            else:
                logger.warning(f"Connection is running but socket not connected. Subscription for {channel} will be sent upon reconnection.")

if __name__ == "__main__":
    def print_callback(message):
        print(f"Received: {json.dumps(message, indent=2)}")

    client = PolyMarketWebsocketClient()
    # 示例 Token ID (来自之前的输出)
    test_token = "53139916998685230938370560473289741425760508848020416029023630402477351897589"
    
    client.subscribe([test_token], callback=print_callback)
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        client.stop()
