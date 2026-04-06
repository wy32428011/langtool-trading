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

    def get_logs(self, address: Optional[str] = None, from_block: Union[str, int] = "earliest", 
                 to_block: Union[str, int] = "latest", topics: List[Any] = None) -> List[Dict[str, Any]]:
        """
        通过 eth_getLogs 获取区块链日志
        
        Args:
            address: 合约地址 (可选)
            from_block: 起始区块 (字符串或区块号)
            to_block: 结束区块 (字符串或区块号)
            topics: Topic 过滤列表 (可选)
            
        Returns:
            List[Dict]: 日志列表
        """
        filter_params = {}
        if from_block is not None:
            filter_params["fromBlock"] = from_block
        if to_block is not None:
            filter_params["toBlock"] = to_block
        if address:
            filter_params["address"] = Web3.to_checksum_address(address)
        if topics:
            filter_params["topics"] = topics
            
        # 使用 web3.eth.get_logs 方法
        # web3.py 会自动处理参数格式映射
        logs = self.w3.eth.get_logs(filter_params)
        
        # 将 AttributeDict 转换为普通字典以保持 API 兼容性，并处理 HexBytes
        result = []
        for log in logs:
            log_dict = dict(log)
            # 处理 topics 列表中的 HexBytes
            if 'topics' in log_dict:
                log_dict['topics'] = [t.hex() if hasattr(t, 'hex') else t for t in log_dict['topics']]
            # 处理其他可能的 HexBytes 字段
            for key, value in log_dict.items():
                if hasattr(value, 'hex'):
                    log_dict[key] = value.hex()
            result.append(log_dict)
        return result

    def call_rpc_method(self, method: str, params: List[Any]) -> Any:
        """
        调用通用的 JSON-RPC 方法（底层使用 web3.py 的管理器）
        
        Args:
            method: RPC 方法名
            params: 参数列表
            
        Returns:
            Any: RPC 方法的响应结果
        """
        return self.w3.provider.make_request(method, params).get('result')

    def is_connected(self) -> bool:
        """
        检查是否已连接到区块链节点
        
        Returns:
            bool: 是否已连接
        """
        return self.w3.is_connected()
