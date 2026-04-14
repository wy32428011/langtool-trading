import requests
from typing import Dict, Any, Optional, List, Union
from web3 import Web3, HTTPProvider
from config import settings

class AlchemyClient:
    """
    Alchemy API 客户端，使用 web3.py 重构，用于与区块链交互。
    Polymarket 部署在 Polygon 网络上。
    """
    
    # Polymarket 核心合约事件 Topic 签名 (keccak256)
    TOPIC_ORDER_FILLED = "0x1d2119cf186a8a37cfc2111100522c0703f8319f688086915f7d29831a2f6430"
    TOPIC_POSITION_SPLIT = "0x1e617d36371752b1156828593e3e00115003c27632644268e378c858548c26f7"
    TOPIC_POSITIONS_MERGE = "0xc7001ca2f4a4753066607a7593c6f1a80809b4f0b240e1b203c9142e01314902"

    def __init__(self, api_key: Optional[str] = None, network: str = "polygon-mainnet"):
        """
        初始化 Alchemy 客户端
        
        Args:
            api_key: Alchemy API Key. 如果未提供，将从 settings 中获取。
            network: 网络名称，默认为 polygon-mainnet。
        """
        self.api_key = api_key or settings.alchemy_api_key
        self.network = network
        self.base_url = f"https://{network}.g.alchemy.com/v2/{self.api_key}"
        
        # 初始化 Web3 实例
        self.w3 = Web3(HTTPProvider(self.base_url))
        
        if not self.w3.is_connected():
            print(f"警告: 无法连接到 Alchemy 节点 ({self.base_url})")

    def get_token_metadata(self, contract_address: str) -> Dict[str, Any]:
        """
        获取代币的元数据 (符号、名称、精度、图标等)
        
        Args:
            contract_address: 代币合约地址
            
        Returns:
            Dict: 包含元数据的字典
        """
        return self.call_rpc_method("alchemy_getTokenMetadata", [contract_address])

    def get_token_balances(self, owner_address: str, contract_addresses: List[str]) -> Dict[str, Any]:
        """
        获取指定地址在特定代币合约中的余额
        
        Args:
            owner_address: 钱包地址
            contract_addresses: 代币合约地址列表
            
        Returns:
            Dict: 包含余额信息的字典
        """
        return self.call_rpc_method("alchemy_getTokenBalances", [owner_address, contract_addresses])

    def get_asset_transfers(self, from_block: str = "0x0", to_block: str = "latest", 
                            from_address: str = None, to_address: str = None,
                            contract_addresses: List[str] = None, category: List[str] = ["erc20"]) -> Dict[str, Any]:
        """
        获取资产转移记录
        
        Args:
            from_block: 起始区块 (十六进制或 "latest"/"earliest")
            to_block: 结束区块 (十六进制或 "latest"/"earliest")
            from_address: 发送者地址 (可选)
            to_address: 接收者地址 (可选)
            contract_addresses: 过滤的合约地址列表 (可选)
            category: 资产类别列表 (如 "external", "internal", "erc20", "erc721", "erc1155")
            
        Returns:
            Dict: 资产转移记录结果
        """
        params = {
            "fromBlock": from_block,
            "toBlock": to_block,
            "category": category,
            "withLog": True
        }
        if from_address:
            params["fromAddress"] = from_address
        if to_address:
            params["toAddress"] = to_address
        if contract_addresses:
            params["contractAddresses"] = contract_addresses
            
        return self.call_rpc_method("alchemy_getAssetTransfers", [params])

    def get_logs(self, address: Optional[Union[str, List[str]]] = None,
                 from_block: Union[str, int] = "earliest",
                 to_block: Union[str, int] = "latest",
                 topics: List[Any] = None,
                 batch_size: int = 10) -> List[Dict[str, Any]]:
        """
        通过 eth_getLogs 获取区块链日志，自动分批以满足 Alchemy 免费套餐限制（10块/请求）

        Args:
            address: 合约地址或地址列表 (可选)
            from_block: 起始区块 (字符串或区块号整数)
            to_block: 结束区块 (字符串或区块号整数)
            topics: Topic 过滤列表 (可选)
            batch_size: 每批请求的区块数，免费套餐最大为 10

        Returns:
            List[Dict]: 日志列表（字段均为字符串，topics 已含 0x 前缀）
        """
        def _to_block_param(b):
            if isinstance(b, int):
                return hex(b)
            return b

        filter_base: Dict[str, Any] = {}
        if address:
            if isinstance(address, list):
                filter_base["address"] = [Web3.to_checksum_address(a) for a in address]
            else:
                filter_base["address"] = Web3.to_checksum_address(address)
        if topics:
            filter_base["topics"] = topics

        # 如果 from_block/to_block 是字符串（如 "latest"），不分批直接请求
        if isinstance(from_block, str) or isinstance(to_block, str):
            filter_base["fromBlock"] = _to_block_param(from_block)
            filter_base["toBlock"] = _to_block_param(to_block)
            return self._rpc_get_logs(filter_base)

        all_logs = []
        for start in range(from_block, to_block + 1, batch_size):
            end = min(start + batch_size - 1, to_block)
            params = {**filter_base, "fromBlock": hex(start), "toBlock": hex(end)}
            all_logs.extend(self._rpc_get_logs(params))
        return all_logs

    def _rpc_get_logs(self, filter_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """直接调用 eth_getLogs JSON-RPC，绕过 web3.py beta 版的编码 bug"""
        result = self._call_rpc("eth_getLogs", [filter_params])
        return result if result else []

    def call_rpc_method(self, method: str, params: List[Any]) -> Any:
        """
        调用通用的 JSON-RPC 方法

        Args:
            method: RPC 方法名
            params: 参数列表

        Returns:
            Any: RPC 方法的响应结果
        """
        return self._call_rpc(method, params)

    def _call_rpc(self, method: str, params: List[Any]) -> Any:
        """底层 JSON-RPC 请求，使用 requests 直接发送"""
        payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
        resp = requests.post(self.base_url, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise Exception(f"RPC error [{data['error']['code']}]: {data['error']['message']}")
        return data.get("result")

    def is_connected(self) -> bool:
        """
        检查是否已连接到区块链节点
        
        Returns:
            bool: 是否已连接
        """
        return self.w3.is_connected()
