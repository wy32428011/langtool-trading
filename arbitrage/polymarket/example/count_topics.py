"""
统计 50000 个 block 内所有日志的 topic 种类及出现次数。
不过滤地址和 topic，仅做统计。
"""
from collections import Counter
from tqdm import tqdm
from web3 import Web3
from arbitrage.polymarket.alchemy_client import AlchemyClient

# ========= 配置 =========
client = AlchemyClient()

CONTRACT_ADDRESS = Web3.to_checksum_address("0x4D97DCd97eC945f40cF65F87097ACe5EA0476045")

START_BLOCK = 81038771
TOTAL_BLOCKS = 50000
BATCH_SIZE = 10   # Alchemy 免费套餐每次最多 10 个 block

# ========= 主流程 =========

def main():
    end_block = START_BLOCK + TOTAL_BLOCKS - 1
    topic_counter: Counter = Counter()
    total_logs = 0

    ranges = range(START_BLOCK, end_block + 1, BATCH_SIZE)

    for start in tqdm(ranges, desc="扫描区块", unit="批"):
        end = min(start + BATCH_SIZE - 1, end_block)
        try:
            logs = client.get_logs(
                address=CONTRACT_ADDRESS,
                from_block=start,
                to_block=end,
                # 不传 topics，统计所有事件种类
            )
        except Exception as e:
            print(f"\n[警告] block {start}-{end} 请求失败: {e}")
            continue

        for log in logs:
            topics = log.get("topics", [])
            if topics:
                topic_counter[topics[0]] += 1   # topics[0] 是事件签名
        total_logs += len(logs)

    print(f"\n=== 统计结果 ===")
    print(f"扫描区块范围 : {START_BLOCK} ~ {end_block}")
    print(f"总日志数     : {total_logs}")
    print(f"Topic 种类数 : {len(topic_counter)}")
    print(f"\n--- Top 30 Topics ---")
    for topic, count in topic_counter.most_common(30):
        print(f"  {topic}  出现 {count} 次")


if __name__ == "__main__":
    main()