import json
import logging
from datetime import datetime
from collections import defaultdict
from tqdm import tqdm
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from sqlalchemy import text
from arbitrage.polymarket.alchemy_client import AlchemyClient
from arbitrage.polymarket.engine import polymarket_engine

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ========= 配置 =========
client = AlchemyClient()
# 注入 Polygon PoA 中间件
client.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

# Polygon USDC（核心资金）
USDC = Web3.to_checksum_address("0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174")

# 事件签名
POSITIONSPLIT_TOPIC = "0x" + client.w3.keccak(
    text="PositionSplit(address,address,bytes32,bytes32,uint256[],uint256)").hex()
POSITIONMERGE_TOPIC = "0x" + client.w3.keccak(
    text="PositionsMerge(address,address,bytes32,bytes32,uint256[],uint256)").hex()

# Polymarket 相关合约
POLYMARKET_CONTRACTS = {
    Web3.to_checksum_address("0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"),  # ConditionalTokens
}

# ========= 数据库操作 =========

def create_trades_table_if_not_exists():
    """创建 polymarket_raw_logs 表"""
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS polymarket_raw_logs (
        transactionHash VARCHAR(128) NOT NULL COMMENT '交易哈希',
        logIndex INT NOT NULL COMMENT '日志索引',
        blockNumber BIGINT COMMENT '区块号',
        blockHash VARCHAR(128) COMMENT '区块哈希',
        transactionIndex INT COMMENT '交易索引',
        address VARCHAR(64) COMMENT '合约地址',
        data TEXT COMMENT '日志数据',
        topics JSON COMMENT '主题列表',
        removed BOOLEAN COMMENT '是否已移除',
        timestamp DATETIME COMMENT '交易时间'
    ) ENGINE=OLAP
    DUPLICATE KEY(transactionHash, logIndex)
    DISTRIBUTED BY HASH(transactionHash) BUCKETS 10
    PROPERTIES (
        "replication_num" = "1",
        "enable_persistent_index" = "true",
        "compression" = "LZ4"
    );
    """
    with polymarket_engine.begin() as conn:
        conn.execute(text(create_table_sql))
            
    logger.info("Table 'polymarket_raw_logs' ensured.")

def save_logs_to_db(logs):
    """批量保存原始日志数据到数据库"""
    if not logs:
        return
    
    insert_sql = text("""
        INSERT INTO polymarket_raw_logs (transactionHash, logIndex, blockNumber, blockHash, transactionIndex, address, data, topics, removed, timestamp)
        VALUES (:transactionHash, :logIndex, :blockNumber, :blockHash, :transactionIndex, :address, :data, :topics, :removed, :timestamp)
    """)
    
    # 预处理数据，处理十六进制和 JSON 序列化
    processed_logs = []
    for log in logs:
        # 转换时间戳
        ts_val = None
        hex_ts = log.get('blockTimestamp')
        if hex_ts:
            try:
                ts_val = datetime.fromtimestamp(int(hex_ts, 16))
            except Exception as e:
                logger.warning(f"Failed to parse timestamp {hex_ts}: {e}")

        processed_logs.append({
            "transactionHash": log.get('transactionHash'),
            "blockNumber": int(log.get('blockNumber', '0x0'), 16),
            "blockHash": log.get('blockHash'),
            "transactionIndex": int(log.get('transactionIndex', '0x0'), 16),
            "logIndex": int(log.get('logIndex', '0x0'), 16),
            "address": log.get('address'),
            "data": log.get('data'),
            "topics": json.dumps(log.get('topics', [])),
            "removed": log.get('removed', False),
            "timestamp": ts_val
        })
    
    with polymarket_engine.begin() as conn:
        conn.execute(insert_sql, processed_logs)
    logger.info(f"Saved {len(processed_logs)} logs to database.")

# ========= 核心逻辑 (不再需要，直接存原始数据) =========

def fetch_and_process_range(from_block, to_block):
    """获取并处理指定范围的日志"""
    logger.info(f"Processing range {from_block} -> {to_block}")
    
    # address_filter = [USDC] + list(POLYMARKET_CONTRACTS)
    address_filter =  list(POLYMARKET_CONTRACTS)
    logs = client.get_logs(
        address=address_filter,
        from_block=from_block,
        to_block=to_block,
        topics=[[POSITIONSPLIT_TOPIC, POSITIONMERGE_TOPIC]], # 只要包含其中之一
        batch_size=10 # 恢复为较小的 batch_size
    )
    
    if not logs:
        return []

    return logs

# ========= 主流程 =========

def main():
    start_block = 81301771
    end_block = 85205510
    
    create_trades_table_if_not_exists()
    
    # 分步处理，避免一次性请求过多数据
    step = 1000
    
    # 测试前 1000 个区块
    test_end = start_block + 100000
    
    total_count = 0
    for current_from in range(start_block, test_end, step):
        current_to = min(current_from + step - 1, test_end)
        logs = fetch_and_process_range(current_from, current_to)
        if logs:
            save_logs_to_db(logs)
            total_count += len(logs)
            logger.info(f"Imported {total_count} logs from test range.")
            
    logger.info(f"Imported {total_count} logs total.")

if __name__ == "__main__":
    main()
