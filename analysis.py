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
        """构建分析提示词"""

        # 将历史数据转换为Markdown表格，提高模型阅读准确性
        history_table = "| 日期 | 开盘 | 最高 | 最低 | 收盘 | 涨跌幅 | 成交量 | 换手率 |\n| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
        # 取最近60天的历史数据，提供更丰富的趋势背景
        for d in history_data[:60]:
            turn_str = f"{d.get('turn', 0)}%" if d.get('turn') else "N/A"
            history_table += f"| {d['date']} | {d['open']} | {d['high']} | {d['low']} | {round(d['close'], 2)} | {d['pctChg']}% | {d['volume']} | {turn_str} |\n"

        prompt = f"""
        你是一位拥有20年实战经验的金牌股票交易员。请根据以下详细的**真实数据**，对股票 {stock_data.get('name', '')} ({stock_data.get('code', '')}) 进行深入的T+1交易机会分析。

        ### ⚠️ 重要指令：
        1. **严禁幻觉**：仅使用下方提供的数据进行分析。如果数据中没有提到的信息，请不要自行编造。
        2. **数据核对**：在给出建议价格前，请务必核对历史最高价、最低价和当前价格，确保建议价格在合理逻辑范围内。
        3. **逻辑严密**：分析过程应直接引用数据指标。

        ### 1. 基本面背景
        - 行业: {stock_info.get('sector', '') if stock_info else '未知'}
        - 市盈率(PE): {current_data.get('pe_ratio', 0)}
        - 市净率(PB): {current_data.get('pb_ratio', 0)}

        ### 2. 实时行情
        - 当前价格: {current_data.get('current_price', 0)}
        - 今日涨跌幅: {current_data.get('change_percent', 0)}%
        - 成交量: {current_data.get('volume_hand', 0)}手
        - 换手率: {current_data.get('turnover_rate', 0)}

        ### 3. 技术指标 (当前)
        - 均线系统: MA5={indicators.get('ma5', 'N/A')}, MA10={indicators.get('ma10', 'N/A')}, MA20={indicators.get('ma20', 'N/A')}, MA60={indicators.get('ma60', 'N/A')}
        - 成交量均线: VMA5={indicators.get('vma5', 'N/A')}, VMA10={indicators.get('vma10', 'N/A')}
        - 强弱指标: RSI(14)={indicators.get('rsi', 'N/A')}
        - 趋势指标: MACD(DIF={indicators.get('macd', 'N/A')}, DEA={indicators.get('macd_signal', 'N/A')}, HIST={indicators.get('macd_hist', 'N/A')})
        - 超买超卖: KDJ(K={indicators.get('kdj_k', 'N/A')}, D={indicators.get('kdj_d', 'N/A')}, J={indicators.get('kdj_j', 'N/A')})
        - 布林带: 上轨={indicators.get('bb_upper', 'N/A')}, 下轨={indicators.get('bb_lower', 'N/A')}
        - 量比 (今日成交量/VMA5): {indicators.get('volume_ratio', 'N/A')}
        - 价格位置: {"股价在MA5之上" if indicators.get('is_above_ma5') else "股价在MA5之下" if indicators.get('is_above_ma5') is not None else "位置待定(MA5未生成)"}, {"股价在MA60之上" if indicators.get('is_above_ma60') else "股价在MA60之下" if indicators.get('is_above_ma60') is not None else "位置待定(MA60未生成)"}
        """
        if settings.enable_factor_analysis:
            prompt += f"\n        - 智能预测因子 (Alpha158): {factor_158:.4f} (该值基于量价多因子模型计算，越高通常代表短期看涨信号越强)\n"

        prompt += f"""
        ### 4. 最近60个交易日历史走势
        {history_table}

        ### 5. 分析要求
        请从以下维度进行专业研判：
        1. **思维链分析**：在输出结论前，先在心中或 `thought_process` 字段中梳理：大盘背景（如有）->均线系统->震荡指标状态->形态识别->风险/收益比。
        2. **趋势分析**：结合均线系统（MA5/MA20/MA60的多头或空头排列）与近60日量价走势，判断当前是处于上涨通道、下跌通道还是震荡筑底。
        3. **技术面共振**：结合 RSI、MACD、KDJ 等指标看是否存在背离、金叉/死叉或超买超卖状态。
        4. **最终决策**：综合Alpha158因子与技术面共振情况，给出T+1日的交易建议。

        ### 6. 输出格式
        请严格按以下JSON格式返回，不要有任何多余的文字说明：
        {{
          "stock_code": "{stock_data.get('code', '')}",
          "stock_name": "{stock_data.get('name', '')}",
          "current_price": {current_data.get('current_price', 0)},
          "thought_process": "此处记录你的详细推理过程，确保逻辑推导自上方数据，无编造内容",
          "analysis": "详细的分析结论摘要",
          "trend": "上涨/下跌/震荡",
          "support": "支撑位价格",
          "resistance": "压力位价格",
          "recommendation": "买入/卖出/观望",
          "action": "详细的交易指令（需包含股票名称和代码，并提供具体的操作逻辑）",
          "predicted_price": "T+1预期目标价",
          "predicted_buy_price": "建议买入入场价",
          "predicted_sell_price": "建议止盈/止损出场价",
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

        # 重命名列头为中文
        column_mapping = {
            'stock_code': '股票代码',
            'stock_name': '股票名称',
            'analysis_time': '分析时间',
            'current_price': '当前价格',
            'alpha158': 'Alpha158因子',
            'thought_process': '推理过程',
            'analysis': '详细结论',
            'trend': '趋势判断',
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

        human_prompt = self._build_human_prompt(stock_data, stock_data, history_data, current_data, indicators, factor_158)

        final_result = ""
        for chunk in llm.stream(
            {"messages": [{"role": "user", "content": human_prompt}]},
            stream_mode="updates"
        ):
            for step, data in chunk.items():
                # 根据原有逻辑提取文本
                try:
                    text = data['messages'][-1].content_blocks[-1]['text']
                    final_result = text
                    print(text)
                except (AttributeError, KeyError, IndexError):
                    # 备用方案：如果结构不同，尝试获取 content
                    if hasattr(data['messages'][-1], 'content'):
                        final_result = data['messages'][-1].content
                        print(final_result)

        # 尝试解析JSON并保存
        if final_result:
            try:
                # 处理可能存在的 markdown 代码块标记
                clean_result = final_result.strip()
                if clean_result.startswith("```json"):
                    clean_result = clean_result[7:]
                elif clean_result.startswith("```"):
                    clean_result = clean_result[3:]
                if clean_result.endswith("```"):
                    clean_result = clean_result[:-3]
                clean_result = clean_result.strip()

                result_dict = json.loads(clean_result)
                
                # 重新构建字典以确保顺序：股票代码和名称排在最前面
                ordered_result = {
                    'stock_code': stock_code,
                    'stock_name': stock_data.get('name', '未知'),
                    'analysis_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'current_price': current_data.get('current_price', 0),
                    'alpha158': factor_158
                }
                # 将 LLM 返回的结果合并进来（排除掉可能重复的 key）
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
                print(f"解析或保存结果失败: {e}")
                print(f"原始结果: {final_result}")
                return None
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

