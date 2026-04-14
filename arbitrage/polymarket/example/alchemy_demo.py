from collections import defaultdict
from tqdm import tqdm
from web3 import Web3
from arbitrage.polymarket.alchemy_client import AlchemyClient

# ========= 配置 =========
client = AlchemyClient()

# Polygon USDC（核心资金）
USDC = Web3.to_checksum_address("0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174")

# Transfer 事件签名
# TRANSFER_TOPIC = "0x" + client.w3.keccak(text="PositionSplit(address,address,uint256)").hex()
POSITIONSPLIT_TOPIC = "0x" + client.w3.keccak(
    text="PositionSplit(address,address,bytes32,bytes32,uint256[],uint256)").hex()
POSITIONMERGE_TOPIC = "0x" + client.w3.keccak(
    text="PositionMerge(address,address,bytes32,bytes32,uint256[],uint256)").hex()

# Polymarket 相关合约
POLYMARKET_CONTRACTS = {
    Web3.to_checksum_address("0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"),  # ConditionalTokens
}

# ========= 工具函数 =========

def parse_transfer(log):
    try:
        from_addr = "0x" + log['topics'][1][-40:]
        to_addr = "0x" + log['topics'][2][-40:]
        amount = int(log['data'], 16) / 1e6

        return {
            "type": "transfer",
            "from": Web3.to_checksum_address(from_addr),
            "to": Web3.to_checksum_address(to_addr),
            "amount": amount,
            "tx_hash": log['transactionHash']
        }
    except:
        return None


def is_polymarket_related(log):
    addr = Web3.to_checksum_address(log['address'])
    return addr in POLYMARKET_CONTRACTS or addr == USDC


# ========= 核心逻辑 =========

def fetch_logs(from_block, to_block):
    print(f"Fetching logs {from_block} -> {to_block}")
    address_filter = [USDC] + list(POLYMARKET_CONTRACTS)
    return client.get_logs(
        address=address_filter,
        from_block=from_block,
        to_block=to_block,
        topics=[POSITIONSPLIT_TOPIC,POSITIONMERGE_TOPIC],
    )


def group_by_tx(logs):
    tx_map = defaultdict(list)
    for log in logs:
        tx_map[log['transactionHash']].append(log)
    return tx_map


def build_trade(tx_logs):
    transfers = [t for log in tx_logs if (t := parse_transfer(log))]

    if not transfers:
        return None

    usdc_out, usdc_in, token_in, token_out = [], [], [], []

    for t in transfers:
        if t["from"] == t["to"] or t["amount"] == 0:
            continue

        log = next((l for l in tx_logs if l['transactionHash'] == t['tx_hash']), None)
        addr = Web3.to_checksum_address(log['address']) if log else None

        if addr == USDC:
            if is_contract(t["to"]):
                usdc_out.append(t)
            else:
                usdc_in.append(t)
        else:
            if is_contract(t["from"]):
                token_in.append(t)
            else:
                token_out.append(t)

    if usdc_out and token_in:
        return {"tx_hash": transfers[0]["tx_hash"], "side": "BUY",
                "amount": usdc_out[0]["amount"], "transfer_count": len(transfers)}
    if usdc_in and token_out:
        return {"tx_hash": transfers[0]["tx_hash"], "side": "SELL",
                "amount": usdc_in[0]["amount"], "transfer_count": len(transfers)}
    return None


def is_contract(addr):
    return addr in POLYMARKET_CONTRACTS


# ========= 主流程 =========

def main():
    from_block = 81038771
    to_block = from_block + 10000

    logs = fetch_logs(from_block, to_block)
    print("Total logs:", len(logs))

    tx_map = group_by_tx(logs)

    trades = []
    for tx_hash, tx_logs in tqdm(tx_map.items()):
        trade = build_trade(tx_logs)
        if trade:
            trades.append(trade)

    print("\n=== Trades ===")
    for t in trades[:20]:
        print(t)


if __name__ == "__main__":
    main()