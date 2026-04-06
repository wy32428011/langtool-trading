import requests

from typing import List, Dict, Any, Optional

from config import settings

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds, TradeParams
from py_clob_client.constants import POLYGON

class PolyMarketClient:
    """
    Polymarket API 客户端工具包
    
    提供与 Polymarket Gamma API 和 CLOB API 交互的方法。
    已集成 py-clob-client SDK，用于处理 CLOB API 的认证、订单簿和成交记录等操作。
    Gamma API 主要用于获取市场和事件的元数据。
    """
    
    GAMMA_API_BASE_URL = "https://gamma-api.polymarket.com"
    CLOB_API_BASE_URL = "https://clob.polymarket.com"

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None, 
                 api_passphrase: Optional[str] = None, private_key: Optional[str] = None,
                 proxies: Optional[Dict[str, str]] = None):
        """
        初始化 Polymarket 客户端
        """
        self.api_key = api_key or settings.poly_api_key
        self.api_secret = api_secret or settings.poly_api_secret
        self.api_passphrase = api_passphrase or settings.poly_api_passphrase
        self.private_key = private_key or settings.poly_private_key
        
        # Gamma API Session
        self.session = requests.Session()
        if proxies:
            self.session.proxies.update(proxies)
        
        # 初始化基础 SDK 客户端 (用于执行 L1 操作)
        self.clob_client = ClobClient(
            host=self.CLOB_API_BASE_URL,
            key=self.private_key,
            chain_id=POLYGON
        )

        # 核心逻辑：如果提供了私钥，先执行 L1 认证以获取/派生 L2 凭据
        if self.private_key:
            try:
                # 获取或派生 API 凭据 (L1 -> L2)
                creds = self.clob_client.create_or_derive_api_creds()
                self.api_key = creds.api_key
                self.api_secret = creds.api_secret
                self.api_passphrase = creds.api_passphrase
                
                # 更新 clob_client 的凭据以执行 L2 操作
                self.clob_client.set_api_creds(creds)
                # print(f"DEBUG: Successfully derived L2 credentials for {self.api_key}")
            except Exception as e:
                # print(f"DEBUG: Failed to derive L2 credentials via L1: {e}")
                # 如果 L1 派生失败且手动提供了 L2 凭据，则手动设置
                if self.api_key and self.api_secret and self.api_passphrase:
                    manual_creds = ApiCreds(
                        api_key=self.api_key,
                        api_secret=self.api_secret,
                        api_passphrase=self.api_passphrase
                    )
                    self.clob_client.set_api_creds(manual_creds)
        elif self.api_key and self.api_secret and self.api_passphrase:
            # 仅提供 L2 凭据的情况
            manual_creds = ApiCreds(
                api_key=self.api_key,
                api_secret=self.api_secret,
                api_passphrase=self.api_passphrase
            )
            self.clob_client.set_api_creds(manual_creds)

    def get_markets(self, limit: int = 100, offset: int = 0, active: bool = True) -> List[Dict[str, Any]]:
        """
        获取市场列表 (Gamma API)
        """
        url = f"{self.GAMMA_API_BASE_URL}/markets"
        params = {
            "limit": limit,
            "offset": offset,
            "active": str(active).lower()
        }
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def get_market_by_id(self, market_id: str) -> Dict[str, Any]:
        """
        通过 ID 获取市场详情 (Gamma API)
        """
        url = f"{self.GAMMA_API_BASE_URL}/markets/{market_id}"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_orderbook(self, token_id: str) -> Dict[str, Any]:
        """
        获取特定 Token 的订单簿 (CLOB API SDK)
        
        :param token_id: 结果 Token 的 ID (Asset ID)
        :return: 包含买单 (bids) 和卖单 (asks) 的字典
        """
        return self.clob_client.get_order_book(token_id)

    def get_orderbooks(self, token_ids: List[str]) -> List[Dict[str, Any]]:
        """
        批量获取多个 Token 的订单簿 (CLOB API SDK)
        
        :param token_ids: 结果 Token ID 的列表
        :return: 订单簿列表
        """
        from py_clob_client.clob_types import BookParams
        params = [BookParams(token_id=tid) for tid in token_ids]
        return self.clob_client.get_order_books(params)

    def get_price_history(self, token_id: str, interval: str = "1h") -> Dict[str, Any]:
        """
        获取价格历史 (CLOB API SDK)
        """
        return self.clob_client.get_price_history(token_id, interval)

    def get_midpoint_price(self, token_id: str) -> float:
        """
        获取 Token 的中间价格 (CLOB API SDK)
        """
        data = self.clob_client.get_midpoint(token_id)
        return float(data.get("price", 0.0))

    def get_events(self, limit: int = 100, offset: int = 0, active: bool = True) -> List[Dict[str, Any]]:
        """
        获取事件列表 (Gamma API)
        """
        url = f"{self.GAMMA_API_BASE_URL}/events"
        params = {
            "limit": limit,
            "offset": offset,
            "active": str(active).lower()
        }
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def get_event_by_id(self, event_id: str) -> Dict[str, Any]:
        """
        通过 ID 获取事件详情 (Gamma API)
        """
        url = f"{self.GAMMA_API_BASE_URL}/events/{event_id}"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_trades(self, maker_address: Optional[str] = None, market: Optional[str] = None, 
                   asset_id: Optional[str] = None,
                   after: Optional[int] = None, before: Optional[int] = None,
                   limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        获取成交记录 (CLOB API SDK)

        :param maker_address: Maker 地址
        :param market: 市场 ID
        :param asset_id: 资产 ID (Token ID)
        :param after: 开始时间戳
        :param before: 结束时间戳
        :param limit: 返回记录的数量限制
        :return: 成交记录列表
        """
        params = TradeParams(
            maker_address=maker_address,
            market=market,
            asset_id=asset_id,
            after=after,
            before=before
        )
        trades = self.clob_client.get_trades(params)
        
        # SDK 的 get_trades 返回结果列表
        if isinstance(trades, list) and limit is not None:
            return trades[:limit]
        
        return trades

    def create_api_key_l1(self) -> Dict[str, Any]:
        """
        使用 L1 签名 (私钥) 创建 API 密钥 (CLOB API SDK)
        """
        if not self.private_key:
            raise ValueError("必须配置 private_key 才能执行 L1 认证操作")
        return self.clob_client.create_api_key()

    def get_api_keys_l1(self) -> List[Dict[str, Any]]:
        """
        使用 L1 签名获取现有的 API 密钥列表 (CLOB API SDK)
        """
        return self.clob_client.get_api_keys()

    def delete_api_key_l1(self) -> Dict[str, Any]:
        """
        使用 L1 签名删除当前 API 密钥 (CLOB API SDK)
        """
        return self.clob_client.delete_api_key()

    def get_sampling_simplified_markets(self) -> List[Dict[str, Any]]:
        """
        获取简化的市场列表 (CLOB API SDK)
        """
        return self.clob_client.get_sampling_simplified_markets()

    def get_sampling_markets(self, next_cursor: str = "") -> Dict[str, Any]:
        """
        获取所有市场的采样数据 (CLOB API SDK)
        """
        return self.clob_client.get_sampling_markets(next_cursor)
