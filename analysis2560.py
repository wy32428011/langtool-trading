import json
import os
import argparse
from datetime import datetime
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
        history_list = []
        # 展示最近60天
        for d in history_data[:60]:
            turn_str = f"{d.get('turn', 0)}%" if d.get('turn') else "N/A"
            history_list.append(
                f"{d['date']}: 开盘={d['open']}, 最高={d['high']}, 最低={d['low']}, 收盘={round(d['close'], 2)}, "
                f"涨跌幅={d['pctChg']}%, 成交量={d['volume']}, 换手率={turn_str}"
            )
        history_summary = "\n".join(history_list)

        prompt = f"""
        你是一位精通“2560战法”的金牌股票交易员。请根据以下数据，利用2560战法对股票 {stock_data.get('name', '')} ({stock_data.get('code', '')}) 进行深度研判。

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
        {history_summary}

        ### 4. 分析要求
        请严格按照2560战法逻辑进行分析：
        1. **趋势研判**：分析MA60和MA25的指向，判断目前是否符合“2560”的入场条件（25线拐头向上，60线走平或向上）。
        2. **买卖点评估**：当前价格相对于25日线和60日线的位置如何？是处于突破期、回踩期还是乖离率过大需要回调？
        3. **量价配合**：近期的上涨是否带量，回调是否缩量？
        4. **最终决策**：给出基于2560战法的明确交易建议。**交易指令(action)应当包含股票名称和代码，且描述应具体详尽，包含具体的操作动作、仓位建议或关键触发条件。**

        ### 5. 输出格式
        请严格按以下JSON格式返回，不要有任何多余的文字说明：
        {{
          "stock_code": "股票代码",
          "stock_name": "股票名称",
          "current_price": "当前价格",
          "strategy_analysis": "基于2560战法的详细分析过程",
          "ma_trend": "MA25与MA60的趋势描述",
          "support": "支撑位价格",
          "resistance": "压力位价格",
          "recommendation": "买入/卖出/观望",
          "action": "详细的交易指令（需包含股票名称和代码，具体到买入点、止损点等）",
          "confidence": 0.0-1.0之间的信心值,
          "risk_warning": "核心风险提示"
        }}
        """
        return prompt

    def _save_to_excel(self, data, filename):
        """将分析结果写入Excel"""
        filepath = os.path.join(self.output_dir, filename)
        df = pd.DataFrame([data])

        column_mapping = {
            'stock_code': '股票代码',
            'stock_name': '股票名称',
            'analysis_time': '分析时间',
            'current_price': '当前价格',
            'ma_trend': '均线趋势',
            'strategy_analysis': '2560战法分析',
            'support': '支撑位',
            'resistance': '压力位',
            'recommendation': '投资建议',
            'action': '交易指令',
            'confidence': '信心值',
            'risk_warning': '风险提示'
        }
        df.rename(columns=column_mapping, inplace=True)
        df.to_excel(filepath, index=False)
        print(f"分析结果已保存至: {filepath}")

    def run(self, stock_code):
        print(f"正在启动 2560 战法分析，股票代码: {stock_code}")
        agent = Agent()
        llm = agent.get_agent()
        database = Database()
        
        stock_data = database.get_stock_info(stock_code)
        if not stock_data:
            print(f"未找到股票代码 {stock_code} 的信息")
            return
            
        history_data = database.get_stock_history(stock_code, 120)
        current_data = database.get_real_time_data(stock_data.get('full_code'))
        indicators = self._calculate_indicators(history_data)
        
        if not indicators:
            print("计算指标失败，可能历史数据不足")
            return

        human_prompt = self._build_human_prompt(stock_data, stock_data, history_data, current_data, indicators)

        print("正在调用大模型进行 2560 战法分析...")
        response = llm.invoke({"messages": [{"role": "user", "content": human_prompt}]})
        
        # 处理结果
        if isinstance(response, dict) and 'messages' in response:
            final_result = response['messages'][-1].content
        else:
            final_result = response.content if hasattr(response, 'content') else str(response)
        
        try:
            # 提取 JSON
            clean_result = final_result.strip()
            if "```json" in clean_result:
                clean_result = clean_result.split("```json")[1].split("```")[0]
            elif "```" in clean_result:
                clean_result = clean_result.split("```")[1].split("```")[0]
            clean_result = clean_result.strip()

            result_dict = json.loads(clean_result)
            result_dict['analysis_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 保存到文件
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"analysis2560_{stock_code}_{timestamp}.xlsx"
            self._save_to_excel(result_dict, filename)
            
            print("\n--- 2560 战法分析结果 ---")
            print(f"股票: {result_dict.get('stock_name')} ({result_dict.get('stock_code')})")
            print(f"建议: {result_dict.get('recommendation')}")
            print(f"指令: {result_dict.get('action')}")
            print(f"分析: {result_dict.get('strategy_analysis')}")
            print("------------------------\n")
            
        except Exception as e:
            print(f"解析大模型输出失败: {e}")
            print(f"原始输出: {final_result}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='A股 2560 战法分析工具')
    parser.add_argument('--code', type=str, required=True, help='股票代码 (如: 601096)')
    args = parser.parse_args()
    
    analyzer = Analysis2560()
    analyzer.run(args.code)
