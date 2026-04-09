from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class Outcome(BaseModel):
    """
    市场结果类
    
    表示一个特定预测市场中的可能结果及其价格。
    """
    name: str = Field(..., description="结果名称")
    price: float = Field(..., description="结果价格 (0.0 到 1.0)")

class Market(BaseModel):
    """
    Polymarket 市场类
    
    封装了从 Gamma API 获取的市场详细信息。
    """
    id: str = Field(..., description="市场的唯一标识符")
    question: str = Field(..., description="预测市场的问题描述")
    condition_id: str = Field(..., description="条件的唯一标识符")
    slug: str = Field(..., description="URL 友好的市场标识符")
    end_date_iso: Optional[str] = Field(None, description="市场结束的 ISO 格式日期")
    description: Optional[str] = Field(None, description="市场的详细描述")
    outcomes: List[str] = Field(..., description="所有可能的结果名称列表")
    outcome_prices: List[float] = Field(..., description="每个结果对应的当前价格列表")
    active: bool = Field(..., description="市场是否处于活跃状态")
    closed: bool = Field(..., description="市场是否已关闭")

class OrderBookLevel(BaseModel):
    """
    订单簿层级类
    
    表示订单簿中特定价格水平的挂单量。
    """
    price: float = Field(..., description="订单价格")
    size: float = Field(..., description="该价格水平的订单数量/深度")

class OrderBook(BaseModel):
    """
    Polymarket 订单簿类
    
    封装了从 CLOB API 获取的特定资产的买卖盘信息。
    """
    bids: List[OrderBookLevel] = Field(..., description="买单列表，按价格从高到低排序")
    asks: List[OrderBookLevel] = Field(..., description="卖单列表，按价格从低到高排序")
    asset_id: str = Field(..., description="资产 (Token) 的唯一标识符")
    timestamp: Optional[str] = Field(None, description="订单簿生成的时间戳")
