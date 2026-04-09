from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
import time

w3 = Web3(Web3.HTTPProvider("https://polygon-mainnet.g.alchemy.com/v2/ikDREBrha4wInFQcaDLwu"))
w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

def find_block_by_timestamp(target_ts):
    latest = w3.eth.block_number
    low = 1
    high = latest

    while low <= high:
        mid = (low + high) // 2
        block = w3.eth.get_block(mid)
        ts = block.timestamp

        if ts < target_ts:
            low = mid + 1
        else:
            high = mid - 1

    return low  # 最接近目标时间的区块

# 2026-01-01 时间戳
target_ts = int(time.mktime(time.strptime("2026-01-01 00:00:00", "%Y-%m-%d %H:%M:%S")))

start_block = find_block_by_timestamp(target_ts)
end_block = w3.eth.block_number

print("start_block:", start_block)
print("end_block:", end_block)