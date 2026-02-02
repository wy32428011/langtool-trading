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
        """构建精简版2560战法分析提示词"""
        # 仅保留最近20天核心数据，移除冗余列以压缩token
        history_table = "| 日期 | 收盘 | 涨跌 | 成交量 |\n| :--- | :--- | :--- | :--- |\n"
        for d in history_data[:20]:
            history_table += f"| {d['date']} | {round(d['close'], 2)} | {d['pctChg']}% | {d['volume']} |\n"

        prompt = f"""
请作为2560战法专家，对 {stock_data.get('name')} ({stock_data.get('code')}) 进行深度研判。
你需要给出基于2560逻辑的 T+1 交易机会分析以及未来一周（5个交易日）的行情走势预测。

2560核心原则：MA60(生命线)需走平或向上；MA25(工作线)向上是买号；股价在均线上方强势；回踩缩量是买点。

数据：
- 行业: {stock_info.get('sector', '未知')} | PE: {current_data.get('pe_ratio', 0)}
- 价格: {current_data.get('current_price')} ({current_data.get('change_percent')}% )
- MA25: {indicators.get('ma25')} ({indicators.get('ma25_trend')})
- MA60: {indicators.get('ma60')} ({indicators.get('ma60_trend')})
- 位置: {"在25线上" if indicators.get('is_above_ma25') else "在25线下"}, {"在60线上" if indicators.get('is_above_ma60') else "在60线下"}
- 量比: {indicators.get('volume_ratio')}

最近20日走势：
{history_table}

要求：
1. 价格预测（建议买入价、建议卖出价/止损价）必须基于25日/60日均线及近期高低点给出精确数值，不得模糊。
2. 必须包含对未来一周（5个交易日）的具体走势预判逻辑。
3. 在得出结论前，必须包含“自我辩驳”环节：针对你给出的2560战法研判，寻找至少一个可能的失效点（如：虚假金叉、量能不足或大盘环境制约）。
4. 结合2560逻辑，严格按以下JSON输出：
{{
  "stock_code": "{stock_data.get('code')}",
  "stock_name": "{stock_data.get('name')}",
  "current_price": {current_data.get('current_price', 0)},
  "thought_process": "简述MA60斜率、MA25位置及量价关系",
  "self_rebuttal": "自我辩驳：寻找2560逻辑下的反向证据或潜在失效点",
  "strategy_analysis": "2560战法要点总结",
  "ma_trend": "均线趋势",
  "weekly_outlook": "未来一周（5个交易日）走势预测及逻辑",
  "support": "支撑位数值",
  "resistance": "压力位数值",
  "suggested_buy_price": 具体的建议买入价数值,
  "suggested_sell_price": 具体的建议止损价数值,
  "recommendation": "买入/观望/卖出",
  "action": "交易指令",
  "confidence": 0-1之间数值,
  "risk_warning": "风险点"
}}
"""
        return prompt.strip()

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
            'self_rebuttal': '自我辩驳',
            'strategy_analysis': '2560战法分析',
            'weekly_outlook': '周度展望',
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

    def _is_promising(self, indicators):
        """
        预筛选逻辑：判断股票是否值得调用 LLM 分析。
        2560 战法核心：60日线需走平或向上，且价格不应远低于60日线。
        """
        if not indicators:
            return False
        
        # 1. 核心前提：MA60 趋势不能向下
        if indicators.get('ma60_trend') == "向下":
            return False
            
        # 2. 价格位置：如果价格远低于 MA60（例如低于 10% 以上），通常不符合 2560 战法的买入形态（回踩或金叉）
        current_price = indicators.get('current_price', 0)
        ma60 = indicators.get('ma60', 0)
        if ma60 > 0 and current_price < ma60 * 0.9:
            return False
            
        # 3. 如果 MA25 和 MA60 都向下，绝对排除
        if indicators.get('ma25_trend') == "向下" and indicators.get('ma60_trend') == "向下":
            return False

        return True

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

        # 增加预筛选逻辑，压缩 token 消耗和提升效率
        if not self._is_promising(indicators):
            print(f"股票 {stock_code} 不符合 2560 基础形态（MA60向下或价格过低），跳过 LLM 分析。")
            return {
                'stock_code': stock_code,
                'stock_name': stock_data.get('name', '未知'),
                'analysis_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'recommendation': '观望',
                'action': '不符合2560战法基础形态，建议继续观察。',
                'thought_process': f"预筛选排除：MA60趋势为 {indicators.get('ma60_trend')}，价格相对于MA60位置为 {'线上' if indicators.get('is_above_ma60') else '线下'}。",
                'confidence': 0.1
            }

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
