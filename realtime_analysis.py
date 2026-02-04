import time
import sys
from datetime import datetime
from analysis import Analysis
from database import Database
from config import settings

def main():
    print("=== 股票实时快速分析工具 (优化版) ===")
    if len(sys.argv) > 1:
        stock_code = sys.argv[1]
    else:
        stock_code = input("请输入需要分析的股票编码 (如 000001): ").strip()
    
    if not stock_code:
        print("错误: 股票编码不能为空")
        return

    db = Database()
    analysis_engine = Analysis()
    
    # 1. 预加载静态/半静态数据
    print(f"正在预加载股票 {stock_code} 的基础数据...")
    stock_data = db.get_stock_info(stock_code)
    if not stock_data:
        print(f"错误: 无法获取股票 {stock_code} 的基本信息。")
        return

    # 获取120天历史数据用于计算指标
    history_data = db.get_stock_history(stock_code, 120)
    if not history_data:
        print(f"错误: 无法获取股票 {stock_code} 的历史数据。")
        return
    
    # 获取智能因子
    factor_158 = 0.0
    if settings.enable_factor_analysis:
        factor_dict = db.get_factor_158([stock_code])
        factor_158 = factor_dict.get(stock_code, 0.0)

    print(f"开始对 {stock_data.get('name')} ({stock_code}) 进行实时监控...")
    print("优化点: 预加载历史数据，增量计算指标，极简 Prompt 快速响应。")
    print("提示: 按 Ctrl+C 停止分析\n")
    
    last_price = 0
    last_analysis_time = 0
    
    try:
        while True:
            # 2. 获取实时数据
            current_data = db.get_real_time_data(stock_data.get('full_code'))
            if not current_data:
                print("等待实时数据...")
                time.sleep(2)
                continue
            
            curr_price = current_data.get('current_price', 0)
            current_time_str = datetime.now().strftime('%H:%M:%S')
            
            # 3. 构造增量 K 线数据并计算指标
            # 将当前实时行情整合进历史数据中，模拟最新的 K 线
            today_k = {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'open': current_data.get('open'),
                'high': current_data.get('high'),
                'low': current_data.get('low'),
                'close': curr_price,
                'volume': current_data.get('volume'),
                'pctChg': current_data.get('change_percent')
            }
            
            # 如果历史数据第一条已经是今天（比如收盘后运行），则替换，否则插入
            temp_history = history_data.copy()
            if temp_history and temp_history[0]['date'] == today_k['date']:
                temp_history[0] = today_k
            else:
                temp_history.insert(0, today_k)
            
            # 计算最新指标
            indicators = analysis_engine._calculate_indicators(temp_history)
            
            # 4. 判断是否需要触发 LLM 分析
            # 策略：价格变化超过 0.1% 或 距离上次分析超过 30 秒
            price_change = abs(curr_price - last_price) / last_price if last_price > 0 else 1
            time_passed = time.time() - last_analysis_time
            
            if price_change >= 0.001 or time_passed >= 30:
                print(f"[{current_time_str}] 价格变动或达到时间阈值，触发 AI 快速研判...")
                
                result = analysis_engine.quick_analysis(
                    stock_code, 
                    stock_data.get('name'), 
                    current_data, 
                    indicators, 
                    factor_158
                )
                
                if result:
                    print("\n" + "="*50)
                    print(f"【实时分析 - {result.get('stock_name')} ({result.get('stock_code')})】")
                    print(f"时间: {result.get('analysis_time')} | 价格: {result.get('current_price')} ({current_data.get('change_percent')}%)")
                    print(f"趋势: {result.get('trend')}")
                    print(f"建议: {result.get('recommendation')} (信心: {int(result.get('confidence', 0)*100)}%)")
                    print(f"核心逻辑: {result.get('thought_process')}")
                    print(f"👉 行动: {result.get('action')}")
                    print("="*50 + "\n")
                    
                    last_price = curr_price
                    last_analysis_time = time.time()
                else:
                    print(f"[{current_time_str}] 警告: 快速分析失败。")
            else:
                # 仅更新显示价格，不调用 LLM
                print(f"[{current_time_str}] 当前价格: {curr_price} ({current_data.get('change_percent')}%) - 走势平稳，监控中...", end='\r')
            
            time.sleep(3) # 缩短基础检查间隔到 3 秒
            
    except KeyboardInterrupt:
        print("\n检测到用户中断，实时分析程序已退出。")
    except Exception as e:
        print(f"\n程序运行出错: {e}")

if __name__ == "__main__":
    main()
