import json
import os
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
from agent import Agent
from database import Database
from config import settings


class Analysis:
    def __init__(self):
        self.data = None
        self.trend = None
        self.support_resistance = None
        self.future_trend = None
        self.risk_factors = None
        self.output_dir = "output"
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def _calculate_indicators(self, history_data):
        """计算技术指标"""
        if not history_data or len(history_data) < 5:
            return {}
        
        # 历史数据是倒序的（最新在前面），为了计算均线需要先正序
        df = pd.DataFrame(history_data[::-1])
        
        # 确保数据类型正确
        df['close'] = pd.to_numeric(df['close'], errors='coerce')
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
        df['high'] = pd.to_numeric(df['high'], errors='coerce')
        df['low'] = pd.to_numeric(df['low'], errors='coerce')

        # 1. 计算价格均线
        df['ma5'] = df['close'].rolling(window=5).mean()
        df['ma10'] = df['close'].rolling(window=10).mean()
        df['ma20'] = df['close'].rolling(window=20).mean()
        df['ma60'] = df['close'].rolling(window=60).mean()
        
        # 2. 计算成交量均线
        df['vma5'] = df['volume'].rolling(window=5).mean()
        df['vma10'] = df['volume'].rolling(window=10).mean()
        
        # 3. 计算 RSI (14)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        # 4. 计算 MACD (12, 26, 9)
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = exp1 - exp2
        df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['hist'] = df['macd'] - df['signal']

        # 5. 计算 KDJ (9, 3, 3)
        low_min = df['low'].rolling(window=9).min()
        high_max = df['high'].rolling(window=9).max()
        rsv = (df['close'] - low_min) / (high_max - low_min) * 100
        df['k'] = rsv.ewm(com=2, adjust=False).mean()
        df['d'] = df['k'].ewm(com=2, adjust=False).mean()
        df['j'] = 3 * df['k'] - 2 * df['d']

        # 6. 计算布林带 Bollinger Bands (20, 2)
        df['bb_mid'] = df['close'].rolling(window=20).mean()
        df['bb_std'] = df['close'].rolling(window=20).std()
        df['bb_upper'] = df['bb_mid'] + (df['bb_std'] * 2)
        df['bb_lower'] = df['bb_mid'] - (df['bb_std'] * 2)

        # 获取最新的一行数据
        latest = df.iloc[-1]
        
        # 返回格式化的指标
        return {
            'ma5': round(float(latest['ma5']), 2) if not pd.isna(latest.get('ma5')) else 0,
            'ma10': round(float(latest['ma10']), 2) if not pd.isna(latest.get('ma10')) else 0,
            'ma20': round(float(latest['ma20']), 2) if not pd.isna(latest.get('ma20')) else 0,
            'ma60': round(float(latest['ma60']), 2) if not pd.isna(latest.get('ma60')) else 0,
            'vma5': round(float(latest['vma5']), 0) if not pd.isna(latest.get('vma5')) else 0,
            'vma10': round(float(latest['vma10']), 0) if not pd.isna(latest.get('vma10')) else 0,
            'rsi': round(float(latest['rsi']), 2) if not pd.isna(latest.get('rsi')) else 50,
            'macd': round(float(latest['macd']), 3) if not pd.isna(latest.get('macd')) else 0,
            'macd_signal': round(float(latest['signal']), 3) if not pd.isna(latest.get('signal')) else 0,
            'macd_hist': round(float(latest['hist']), 3) if not pd.isna(latest.get('hist')) else 0,
            'kdj_k': round(float(latest['k']), 2) if not pd.isna(latest.get('k')) else 0,
            'kdj_d': round(float(latest['d']), 2) if not pd.isna(latest.get('d')) else 0,
            'kdj_j': round(float(latest['j']), 2) if not pd.isna(latest.get('j')) else 0,
            'bb_upper': round(float(latest['bb_upper']), 2) if not pd.isna(latest.get('bb_upper')) else 0,
            'bb_lower': round(float(latest['bb_lower']), 2) if not pd.isna(latest.get('bb_lower')) else 0,
            'is_above_ma5': bool(latest['close'] > latest['ma5']) if not pd.isna(latest.get('ma5')) else None,
            'is_above_ma10': bool(latest['close'] > latest['ma10']) if not pd.isna(latest.get('ma10')) else None,
            'is_above_ma20': bool(latest['close'] > latest['ma20']) if not pd.isna(latest.get('ma20')) else None,
            'is_above_ma60': bool(latest['close'] > latest['ma60']) if not pd.isna(latest.get('ma60')) else None,
            'volume_ratio': round(float(latest['volume'] / latest['vma5']), 2) if not pd.isna(latest.get('vma5')) and latest['vma5'] > 0 else 0
        }

    def _build_human_prompt(self, stock_data, stock_info, history_data, current_data, indicators, factor_158):
        """构建精简版分析提示词"""
        # 仅保留最近20天核心数据，移除冗余列以压缩token
        history_table = "| 日期 | 收盘 | 涨跌 | 成交量 |\n| :--- | :--- | :--- | :--- |\n"
        for d in history_data[:20]:
            history_table += f"| {d['date']} | {round(d['close'], 2)} | {d['pctChg']}% | {d['volume']} |\n"

        prompt = f"""
请作为资深交易员，对 {stock_data.get('name')} ({stock_data.get('code')}) 进行深度研判。
你需要给出 T+1 交易机会分析以及未来一周（5个交易日）的行情走势预测。

数据：
- 行业: {stock_info.get('sector', '未知')} | PE: {current_data.get('pe_ratio', 0)}
- 价格: {current_data.get('current_price')} ({current_data.get('change_percent')}% )
- 均线: MA5:{indicators.get('ma5')}, MA20:{indicators.get('ma20')}, MA60:{indicators.get('ma60')}
- 指标: MACD:{indicators.get('macd_hist')}, RSI:{indicators.get('rsi')}, KDJ:{indicators.get('kdj_j')}
- 位置: {"MA5之上" if indicators.get('is_above_ma5') else "MA5之下"}, {"MA60之上" if indicators.get('is_above_ma60') else "MA60之下"}
- 量比: {indicators.get('volume_ratio')}
"""
        if settings.enable_factor_analysis:
            prompt += f"- 预测因子: {factor_158:.4f}\n"

        prompt += f"""
最近20日走势：
{history_table}

要求：
1. 价格预测（目标价、入场价、止损价）必须基于上述技术指标和波段高低点给出精确的数值点位，严禁给出“XX元附近”等模糊表述。
2. 必须包含对未来一周（5个交易日）的走势预判逻辑。
3. 在得出结论前，必须包含“自我辩驳”环节：针对你给出的主要趋势研判，寻找至少一个反向证据或潜在失效场景。
4. 严格按以下JSON格式输出分析结果：
{{
  "stock_code": "{stock_data.get('code')}",
  "stock_name": "{stock_data.get('name')}",
  "current_price": {current_data.get('current_price', 0)},
  "thought_process": "简述趋势、指标及量价逻辑",
  "self_rebuttal": "自我辩驳：寻找反向证据或潜在失效逻辑",
  "analysis": "核心结论",
  "trend": "趋势状态",
  "weekly_outlook": "对未来一周（5个交易日）的具体走势预测及逻辑",
  "support": "支撑位数值",
  "resistance": "压力位数值",
  "recommendation": "买入/观望/卖出",
  "action": "交易指令",
  "predicted_price": 具体的预期目标价数值,
  "predicted_buy_price": 具体的建议买入价数值,
  "predicted_sell_price": 具体的建议止损价数值,
  "confidence": 0-1之间数值,
  "risk_warning": "具体风险点"
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

        # 重命名列头为中文
        column_mapping = {
            'stock_code': '股票代码',
            'stock_name': '股票名称',
            'analysis_time': '分析时间',
            'current_price': '当前价格',
            'alpha158': 'Alpha158因子',
            'thought_process': '推理过程',
            'self_rebuttal': '自我辩驳',
            'analysis': '详细结论',
            'trend': '趋势判断',
            'weekly_outlook': '周度展望',
            'support': '支撑位',
            'resistance': '压力位',
            'recommendation': '投资建议',
            'action': '操作动作',
            'predicted_price': '预期目标价',
            'predicted_buy_price': '建议买入价格',
            'predicted_sell_price': '建议卖出价格',
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

    def _is_promising(self, indicators, factor_158):
        """
        预筛选逻辑：判断股票是否值得调用 LLM 分析。
        """
        if not indicators:
            return False
            
        # 1. 如果 Alpha158 因子极低（例如小于 -0.5），通常短期走势极弱
        if factor_158 < -0.5:
            return False
            
        # 2. 强空头排列：MA5 < MA20 < MA60 且价格在 MA5 之下，且 MA5 还在向下
        ma5 = indicators.get('ma5', 0)
        ma20 = indicators.get('ma20', 0)
        ma60 = indicators.get('ma60', 0)
        
        if ma5 < ma20 < ma60 and not indicators.get('is_above_ma5'):
            # 如果 MACD 还在放绿柱，说明跌势未止
            if indicators.get('macd_hist', 0) < 0:
                return False
                
        return True

    def analysis_stock(self, stock_code, save_to_file=True):
        agent = Agent()
        llm = agent.get_agent()
        database = Database()
        stock_data = database.get_stock_info(stock_code)
        if not stock_data:
            print(f"未找到股票代码 {stock_code} 的信息")
            return None
            
        history_data = database.get_stock_history(stock_code, 120)
        current_data = database.get_real_time_data(stock_data.get('full_code'))
        
        # 计算技术指标
        indicators = self._calculate_indicators(history_data)
        
        # 获取智能因子
        factor_158 = 0.0
        if settings.enable_factor_analysis:
            factor_158_dict = database.get_factor_158([stock_code])
            factor_158 = factor_158_dict.get(stock_code, 0.0)

        # 增加预筛选逻辑，节省 Token 和时间
        if not self._is_promising(indicators, factor_158):
            print(f"股票 {stock_code} 趋势过弱或因子评分过低，跳过 LLM 分析。")
            result_dict = {
                'stock_code': stock_code,
                'stock_name': stock_data.get('name', '未知'),
                'analysis_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'current_price': current_data.get('current_price', 0) if current_data else 0,
                'alpha158': factor_158,
                'recommendation': '观望',
                'trend': '下跌/空头',
                'thought_process': '预筛选机制拦截：指标显示强空头排列或 Alpha158 因子评分极低，暂无参与价值。',
                'action': '保持观望，等待趋势反转或缩量筑底。',
                'confidence': 0.1
            }
            if save_to_file:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"analysis_{stock_code}_{timestamp}.xlsx"
                self._save_to_excel(result_dict, filename)
            return result_dict

        human_prompt = self._build_human_prompt(stock_data, stock_data, history_data, current_data, indicators, factor_158)

        print(f"正在分析 {stock_code}...")
        try:
            response = llm.invoke({"messages": [{"role": "user", "content": human_prompt}]})
            
            # 处理结果
            if isinstance(response, dict) and 'messages' in response:
                final_result = response['messages'][-1].content
            else:
                final_result = response.content if hasattr(response, 'content') else str(response)
            print(final_result)
            # 尝试解析 JSON
            clean_result = final_result.strip()
            if clean_result.startswith("```json"):
                clean_result = clean_result[7:]
            elif clean_result.startswith("```"):
                clean_result = clean_result[3:]
            if clean_result.endswith("```"):
                clean_result = clean_result[:-3]
            clean_result = clean_result.strip()

            result_dict = json.loads(clean_result)
            
            # 重新构建字典以确保顺序
            ordered_result = {
                'stock_code': stock_code,
                'stock_name': stock_data.get('name', '未知'),
                'analysis_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'current_price': current_data.get('current_price', 0) if current_data else 0,
                'alpha158': factor_158
            }
            # 合并 LLM 结果
            for key, value in result_dict.items():
                if key not in ordered_result:
                    ordered_result[key] = value
            
            result_dict = ordered_result

            if save_to_file:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"analysis_{stock_code}_{timestamp}.xlsx"
                self._save_to_excel(result_dict, filename)
            
            return result_dict

        except Exception as e:
            print(f"分析股票 {stock_code} 失败: {e}")
            return None
    
    def batch_analysis(self, max_workers=5):
        """批量分析所有股票，多线程执行"""
        from concurrent.futures import as_completed
        database = Database()
        stock_codes = database.get_all_stock_codes()
        print(f"获取到 {len(stock_codes)} 只股票，开始多线程批量分析 (max_workers={max_workers})...")
        
        start_time = time.time()  # 记录开始时间
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"batch_analysis_{timestamp}.xlsx"
        
        valid_results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_code = {executor.submit(self.analysis_stock, code, save_to_file=False): code for code in stock_codes}
            
            # 随着任务完成获取结果并立即写入
            for future in as_completed(future_to_code):
                code = future_to_code[future]
                try:
                    result = future.result()
                    if result and isinstance(result, dict):
                        # 每次得到新结果立即追加保存，实现“先生成先写入”且不覆盖已有内容
                        is_first = len(valid_results) == 0
                        self._save_to_excel(result, filename, append=not is_first)
                        valid_results.append(result)
                except Exception as e:
                    print(f"分析股票 {code} 时发生异常: {e}")
        
        end_time = time.time()  # 记录结束时间
        duration = end_time - start_time
        
        if valid_results:
            print(f"批量分析完成，共成功分析 {len(valid_results)} 只股票。")
        else:
            print("批量分析完成，但未获取到任何有效结果。")
        
        print(f"整个过程分析完成，总耗时: {duration:.2f} 秒 (约 {duration/60:.2f} 分钟)")
        print(f"完整分析结果已保存至: output/{filename}")

        if valid_results:
            # 重新按信心值排序并覆盖保存一次完整版
            valid_results.sort(key=lambda x: x.get('confidence', 0), reverse=True)
            self._save_to_excel(valid_results, filename, append=False)
            
            # 筛选建议买入的股票
            buy_stocks = [r for r in valid_results if r.get('recommendation') and '买入' in str(r.get('recommendation'))]
            
            if buy_stocks:
                print(f"\n=== 发现建议买入的精选股票 ({len(buy_stocks)} 只) ===")
                for stock in buy_stocks:
                    print(f"代码: {stock.get('stock_code')} | 名称: {stock.get('stock_name')} | 建议: {stock.get('recommendation')} | 信心值: {stock.get('confidence')}")
                
                # 保存筛选后的结果到单独的 Excel
                selected_filename = f"selected_analysis_{timestamp}.xlsx"
                self._save_to_excel(buy_stocks, selected_filename)
                print(f"精选股票已保存至: output/{selected_filename}")
            else:
                print("\n本次分析未发现明确建议买入的股票。")

