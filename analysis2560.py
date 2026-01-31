import json
import os
import argparse
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
from agent import Agent
from database import Database
from config import settings

class Analysis2560:
    def __init__(self):
        self.output_dir = "output"
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def _calculate_indicators(self, history_data):
        """计算2560战法核心指标"""
        if not history_data or len(history_data) < 60:
            return {}
        
        # 历史数据是倒序的（最新在前面），为了计算均线需要先正序
        df = pd.DataFrame(history_data[::-1])
        
        # 确保数据类型正确
        df['close'] = pd.to_numeric(df['close'], errors='coerce')
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce')

        # 1. 计算核心均线：25日和60日
        df['ma25'] = df['close'].rolling(window=25).mean()
        df['ma60'] = df['close'].rolling(window=60).mean()
        
        # 2. 计算均线斜率（趋势）- 使用最近3天的变化来判断方向
        df['ma25_change'] = df['ma25'].diff(3)
        df['ma60_change'] = df['ma60'].diff(3)

        # 3. 计算成交量均线
        df['vma5'] = df['volume'].rolling(window=5).mean()

        latest = df.iloc[-1]
        
        return {
            'ma25': round(float(latest['ma25']), 2) if not pd.isna(latest.get('ma25')) else 0,
            'ma60': round(float(latest['ma60']), 2) if not pd.isna(latest.get('ma60')) else 0,
            'ma25_trend': "向上" if latest['ma25_change'] > 0 else "向下" if latest['ma25_change'] < 0 else "走平",
            'ma60_trend': "向上" if latest['ma60_change'] > 0 else "向下" if latest['ma60_change'] < 0 else "走平",
            'is_above_ma25': bool(latest['close'] > latest['ma25']) if not pd.isna(latest.get('ma25')) else None,
            'is_above_ma60': bool(latest['close'] > latest['ma60']) if not pd.isna(latest.get('ma60')) else None,
            'vma5': round(float(latest['vma5']), 0) if not pd.isna(latest.get('vma5')) else 0,
            'volume_ratio': round(float(latest['volume'] / latest['vma5']), 2) if not pd.isna(latest.get('vma5')) and latest['vma5'] > 0 else 0,
            'current_price': round(float(latest['close']), 2)
        }

    def _build_human_prompt(self, stock_data, stock_info, history_data, current_data, indicators):
        """构建2560战法分析提示词"""
        # 将历史数据转换为Markdown表格，提高模型阅读准确性
        history_table = "| 日期 | 开盘 | 最高 | 最低 | 收盘 | 涨跌幅 | 成交量 | 换手率 |\n| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
        # 展示最近60天
        for d in history_data[:60]:
            turn_str = f"{d.get('turn', 0)}%" if d.get('turn') else "N/A"
            history_table += f"| {d['date']} | {d['open']} | {d['high']} | {d['low']} | {round(d['close'], 2)} | {d['pctChg']}% | {d['volume']} | {turn_str} |\n"

        prompt = f"""
        你是一位精通“2560战法”的金牌股票交易员。请根据以下提供的**真实数据**，利用2560战法对股票 {stock_data.get('name', '')} ({stock_data.get('code', '')}) 进行深度研判。

        ### ⚠️ 重要指令：
        1. **严禁幻觉**：仅使用下方提供的数据进行分析。如果数据中没有提到的信息，请不要自行编造。
        2. **数据核对**：在给出建议价格前，请务必核对历史最高价、最低价和当前价格，确保建议价格在合理逻辑范围内。
        3. **逻辑严密**：分析过程应直接引用数据指标（如“当前价格低于MA25”，而不是模糊的“价格走弱”）。

        ### 2560战法核心原则：
        1. **60日均线 (MA60)**：生命线，决定中长期趋势。60日线向上或走平是做多的前提。
        2. **25日均线 (MA25)**：工作线，决定中期强度。25日线拐头向上是重要的买入信号。
        3. **量价关系**：股价在25日和60日线上方运行为强势；回踩均线不破且缩量是极佳买点。
        4. **形态配合**：关注25日线与60日线的金叉、回踩确认等形态。

        ### 1. 基本面背景
        - 行业: {stock_info.get('sector', '') if stock_info else '未知'}
        - 市盈率(PE): {current_data.get('pe_ratio', 0)}
        - 市净率(PB): {current_data.get('pb_ratio', 0)}

        ### 2. 实时行情与2560指标
        - 当前价格: {current_data.get('current_price', 0)}
        - 今日涨跌幅: {current_data.get('change_percent', 0)}%
        - MA25: {indicators.get('ma25', 'N/A')} (趋势: {indicators.get('ma25_trend', '未知')})
        - MA60: {indicators.get('ma60', 'N/A')} (趋势: {indicators.get('ma60_trend', '未知')})
        - 价格位置: {"在25日线上方" if indicators.get('is_above_ma25') else "在25日线下方"}, {"在60日线上方" if indicators.get('is_above_ma60') else "在60日线下方"}
        - 量比: {indicators.get('volume_ratio', 'N/A')}

        ### 3. 最近60个交易日走势
        {history_table}

        ### 4. 分析要求
        请严格按照2560战法逻辑进行分析：
        1. **思维链分析**：在输出结论前，先在心中或 `thought_process` 字段中梳理：MA60斜率->MA25位置->当前价格与均线乖离率->近期量能变化。
        2. **趋势研判**：分析MA60和MA25的指向，判断目前是否符合“2560”的入场条件（25线拐头向上，60线走平或向上）。
        3. **买卖点评估**：当前价格相对于25日线和60日线的位置如何？是处于突破期、回踩期还是乖离率过大需要回调？
        4. **最终决策**：给出基于2560战法的明确交易建议。

        ### 5. 输出格式
        请严格按以下JSON格式返回，不要有任何多余的文字说明：
        {{
          "stock_code": "{stock_data.get('code', '')}",
          "stock_name": "{stock_data.get('name', '')}",
          "current_price": {current_data.get('current_price', 0)},
          "thought_process": "此处记录你的详细推理过程，确保逻辑推导自上方数据，无编造内容",
          "strategy_analysis": "基于2560战法的详细分析过程摘要",
          "ma_trend": "MA25与MA60的趋势描述",
          "support": "支撑位价格",
          "resistance": "压力位价格",
          "suggested_buy_price": "建议买入价格区间",
          "suggested_sell_price": "建议卖出/止损价格区间",
          "recommendation": "买入/卖出/观望",
          "action": "详细的交易指令（需包含股票名称和代码，具体到买入点、止损点等）",
          "confidence": 0.0-1.0之间的信心值,
          "risk_warning": "核心风险提示"
        }}
        """
        return prompt

    def _save_to_excel(self, data, filename, append=False):
        """将分析结果写入Excel"""
        filepath = os.path.join(self.output_dir, filename)

        # 将字典或列表转换为DataFrame
        if isinstance(data, list):
            df = pd.DataFrame(data)
        else:
            df = pd.DataFrame([data])

        column_mapping = {
            'stock_code': '股票代码',
            'stock_name': '股票名称',
            'analysis_time': '分析时间',
            'current_price': '当前价格',
            'ma_trend': '均线趋势',
            'thought_process': '推理过程',
            'strategy_analysis': '2560战法分析',
            'support': '支撑位',
            'resistance': '压力位',
            'suggested_buy_price': '建议买入价格',
            'suggested_sell_price': '建议卖出价格',
            'recommendation': '投资建议',
            'action': '交易指令',
            'confidence': '信心值',
            'risk_warning': '风险提示'
        }
        
        # 确保所有列都存在且顺序一致
        for col in column_mapping.keys():
            if col not in df.columns:
                df[col] = ""
        
        # 按照映射顺序重排
        df = df[list(column_mapping.keys())]
        
        df.rename(columns=column_mapping, inplace=True)

        # 写入Excel
        if append and os.path.exists(filepath):
            try:
                with pd.ExcelWriter(filepath, engine='openpyxl', mode='a', if_sheet_exists='overlay') as writer:
                    # 尝试写入现有工作表的末尾
                    try:
                        startrow = writer.book['Sheet1'].max_row
                        df.to_excel(writer, index=False, header=False, startrow=startrow)
                    except KeyError:
                        # 如果Sheet1不存在，则正常写入
                        df.to_excel(writer, index=False)
            except Exception as e:
                print(f"追加写入Excel失败: {e}，尝试重新覆盖写入")
                df.to_excel(filepath, index=False)
        else:
            df.to_excel(filepath, index=False)

        print(f"分析结果已保存至: {filepath}")
        return filepath

    def run(self, stock_code, save_to_file=True):
        print(f"正在启动 2560 战法分析，股票代码: {stock_code}")
        agent = Agent()
        llm = agent.get_agent()
        database = Database()
        
        stock_data = database.get_stock_info(stock_code)
        if not stock_data:
            print(f"未找到股票代码 {stock_code} 的信息")
            return None
            
        history_data = database.get_stock_history(stock_code, 120)
        current_data = database.get_real_time_data(stock_data.get('full_code'))
        indicators = self._calculate_indicators(history_data)
        
        if not indicators:
            print("计算指标失败，可能历史数据不足")
            return None

        human_prompt = self._build_human_prompt(stock_data, stock_data, history_data, current_data, indicators)

        print(f"正在调用大模型进行 2560 战法分析 ({stock_code})...")
        try:
            response = llm.invoke({"messages": [{"role": "user", "content": human_prompt}]})
            
            # 处理结果
            if isinstance(response, dict) and 'messages' in response:
                final_result = response['messages'][-1].content
            else:
                final_result = response.content if hasattr(response, 'content') else str(response)
            print(f"大模型原始响应: {final_result}")
            # 提取 JSON
            clean_result = final_result.strip()
            if clean_result.startswith("```json"):
                clean_result = clean_result[7:]
            elif clean_result.startswith("```"):
                clean_result = clean_result[3:]
            if clean_result.endswith("```"):
                clean_result = clean_result[:-3]
            clean_result = clean_result.strip()

            # 处理可能被截断的 JSON
            if not clean_result.endswith("}"):
                print("检测到 JSON 可能被截断，尝试修复...")
                # 寻找最后一个完整的字段或尝试闭合
                if '"' in clean_result:
                    # 如果是以引号结尾，可能是在字符串中间截断
                    last_quote_idx = clean_result.rfind('"')
                    if last_quote_idx > clean_result.rfind(':'):
                        # 在字符串内截断，补全引号和括号
                        clean_result = clean_result[:last_quote_idx+1] + '"}'
                    else:
                        clean_result += '"}'
                else:
                    clean_result += "}"

            try:
                result_dict = json.loads(clean_result)
            except json.JSONDecodeError:
                # 尝试更激进的 JSON 提取
                import re
                json_match = re.search(r'\{.*\}', clean_result, re.DOTALL)
                if json_match:
                    try:
                        result_dict = json.loads(json_match.group())
                    except json.JSONDecodeError:
                        # 仍然失败，尝试手动修复常见的截断问题
                        fixed_json = json_match.group()
                        if not fixed_json.endswith("}"):
                            fixed_json += '"}' # 假设是在字符串处截断
                        try:
                            result_dict = json.loads(fixed_json)
                        except:
                            raise
                else:
                    raise

            result_dict['analysis_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            if save_to_file:
                # 保存到文件
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"analysis2560_{stock_code}_{timestamp}.xlsx"
                self._save_to_excel(result_dict, filename)
            
            # 单股模式下打印简要结果
            if save_to_file:
                print(f"\n--- 2560 战法分析结果 ({stock_code}) ---")
                print(f"股票: {result_dict.get('stock_name')} ({result_dict.get('stock_code')})")
                print(f"建议: {result_dict.get('recommendation')}")
                print(f"建议买入价格: {result_dict.get('suggested_buy_price')}")
                print(f"建议卖出价格: {result_dict.get('suggested_sell_price')}")
                print(f"指令: {result_dict.get('action')}")
                print("------------------------\n")

            return result_dict
            
        except Exception as e:
            print(f"分析股票 {stock_code} 失败: {e}")
            if 'final_result' in locals():
                print(f"原始输出: {final_result}")
            return None

    def batch_analysis(self, max_workers=5):
        """批量分析所有股票，多线程执行"""
        database = Database()
        stock_codes = database.get_all_stock_codes()
        print(f"获取到 {len(stock_codes)} 只股票，开始多线程批量 2560 分析 (max_workers={max_workers})...")
        
        start_time = time.time()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"batch_analysis2560_{timestamp}.xlsx"
        
        valid_results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_code = {executor.submit(self.run, code, save_to_file=False): code for code in stock_codes}
            
            for future in as_completed(future_to_code):
                code = future_to_code[future]
                try:
                    result = future.result()
                    if result and isinstance(result, dict):
                        valid_results.append(result)
                        # 实时保存，防止中断丢失全部结果
                        is_first = len(valid_results) == 1
                        self._save_to_excel(result, filename, append=not is_first)
                except Exception as e:
                    print(f"分析股票 {code} 时发生异常: {e}")
        
        duration = time.time() - start_time
        print(f"\n2560 批量分析完成，共成功分析 {len(valid_results)} 只股票。")
        print(f"总耗时: {duration:.2f} 秒 (约 {duration/60:.2f} 分钟)")
        print(f"完整分析结果已保存至: output/{filename}")
        
        if valid_results:
            # 重新按信心值排序并覆盖保存一次完整版
            valid_results.sort(key=lambda x: x.get('confidence', 0), reverse=True)
            self._save_to_excel(valid_results, filename, append=False)
            
            # 筛选符合2560战法的股票（投资建议为“买入”）
            buy_stocks = [r for r in valid_results if r.get('recommendation') and '买入' in str(r.get('recommendation'))]
            
            if buy_stocks:
                print(f"\n=== 发现符合 2560 战法（建议买入）的股票 ({len(buy_stocks)} 只) ===")
                for stock in buy_stocks:
                    print(f"代码: {stock.get('stock_code')} | 名称: {stock.get('stock_name')} | 建议: {stock.get('recommendation')} | 信心值: {stock.get('confidence')}")
                
                # 保存筛选后的结果到单独的 Excel
                selected_filename = f"selected_2560_{timestamp}.xlsx"
                self._save_to_excel(buy_stocks, selected_filename)
                print(f"符合条件的精选股票已保存至: output/{selected_filename}")
            else:
                print("\n本次分析未发现符合建议买入条件的股票。")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='A股 2560 战法分析工具')
    parser.add_argument('--code', type=str, required=True, help='股票代码 (如: 601096)')
    args = parser.parse_args()
    
    analyzer = Analysis2560()
    analyzer.run(args.code)
