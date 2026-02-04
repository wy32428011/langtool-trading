import time
import sys
from datetime import datetime
from analysis import Analysis

def main():
    print("=== 股票实时分析工具 ===")
    if len(sys.argv) > 1:
        stock_code = sys.argv[1]
    else:
        stock_code = input("请输入需要分析的股票编码 (如 000001): ").strip()
    
    if not stock_code:
        print("错误: 股票编码不能为空")
        return

    analysis_engine = Analysis()
    from database import Database
    db = Database()
    stock_data = db.get_stock_info(stock_code)
    
    if not stock_data:
        print(f"错误: 无法获取股票 {stock_code} 的基本信息，请检查代码是否正确。")
        return

    print(f"开始对股票 {stock_data.get('name')} ({stock_code}) 进行实时分析...")
    print("提示: 按 Ctrl+C 可以停止分析\n")
    
    try:
        while True:
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"[{current_time}] 正在抓取实时数据并进行大模型分析...")
            
            # 调用已有的分析逻辑
            # 在实时循环中，我们默认不为每次分析生成独立的 Excel 文件，以免产生过多文件
            result = analysis_engine.analysis_stock(stock_code, save_to_file=False)
            
            if result:
                print("\n" + "="*50)
                print(f"【分析结果 - {result.get('stock_name')} ({result.get('stock_code')})】")
                print(f"当前时间: {result.get('analysis_time')}")
                print(f"当前价格: {result.get('current_price')}")
                print(f"智能因子 (Alpha158): {result.get('alpha158', 'N/A')}")
                print("-" * 20)
                print(f"市场建议: {result.get('recommendation', '未知')}")
                print(f"趋势研判: {result.get('trend', '未知')}")
                print(f"信心指数: {result.get('confidence', 0) * 100}%")
                print(f"行动指南: {result.get('action', '无')}")
                print(f"深度思考: {result.get('thought_process', '无')}")
                print("="*50 + "\n")
            else:
                print(f"[{current_time}] 警告: 分析失败，请检查网络连接或股票代码是否正确。")
            
            # 设置循环间隔，默认 60 秒一次
            # 也可以根据需求调整频率
            time.sleep(10)
            
    except KeyboardInterrupt:
        print("\n检测到用户中断，实时分析程序已退出。")
    except Exception as e:
        print(f"\n程序运行出错: {e}")

if __name__ == "__main__":
    main()
