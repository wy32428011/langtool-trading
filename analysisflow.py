import operator
import json
import os
from datetime import datetime
from typing import Annotated, TypedDict, Union

import pandas as pd
from langgraph.graph import StateGraph, END, START

from agent import Agent
from database import Database
from langchain_core.messages import HumanMessage, SystemMessage
from config import settings

# 定义状态结构
class AgentState(TypedDict):
    stock_code: str
    stock_info: dict
    history_data: list
    real_time_data: dict
    indicators: dict
    alpha158: float
    fundamental_analysis: str
    technical_analysis: str
    final_result: dict

class AnalysisFlow:
    def __init__(self):
        self.agent = Agent()
        # 直接使用 agent 里的 model
        self.llm = self.agent.model
        self.db = Database()
        self.output_dir = "output"
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def fundamental_analyst_node(self, state: AgentState):
        """金牌股票基本面分析师节点"""
        stock_info = state.get('stock_info', {})
        real_time_data = state.get('real_time_data', {})
        
        prompt = f"""
请分析 {stock_info.get('name')} ({state['stock_code']}) 基本面。

数据：
- 行业: {stock_info.get('sector', '未知')}
- PE: {real_time_data.get('pe_ratio', 'N/A')} | PB: {real_time_data.get('pb_ratio', 'N/A')}
- 业务: {stock_info.get('description', '暂无')}

分析其行业地位、估值及风险。
"""
        
        messages = [
            SystemMessage(content="你是一位资深基本面分析师。"),
            HumanMessage(content=prompt)
        ]
        
        print(f"[{state['stock_code']}] 基本面分析师正在工作...")
        response = self.llm.invoke(messages)
        return {"fundamental_analysis": response.content}

    def technical_analyst_node(self, state: AgentState):
        """金牌资深股票数据分析师节点"""
        history_data = state.get('history_data', [])
        indicators = state.get('indicators', {})
        alpha158 = state.get('alpha158', 0.0)
        
        # 精简历史数据：展示最近20天核心列
        history_list = []
        for d in history_data[:20]:
            history_list.append(
                f"{d['date']}: 收盘={round(d['close'], 2)}, 涨跌={d['pctChg']}%, 量={d['volume']}"
            )
        history_summary = "\n".join(history_list)
        
        prompt = f"""
请作为资深分析师分析 {state['stock_code']} 的技术面。

数据：
- 均线: MA5:{indicators.get('ma5')}, MA10:{indicators.get('ma10')}, MA20:{indicators.get('ma20')}
- 指标: 量比:{indicators.get('volume_ratio')}, Alpha158:{alpha158:.4f}
- 最近20日走势：
{history_summary}

请分析趋势、量价及Alpha158信号。
"""
        
        messages = [
            SystemMessage(content="你是一位金牌资深股票数据分析师。"),
            HumanMessage(content=prompt)
        ]
        
        print(f"[{state['stock_code']}] 数据分析师正在工作...")
        response = self.llm.invoke(messages)
        return {"technical_analysis": response.content}

    def trader_node(self, state: AgentState):
        """金牌资深股票交易员节点"""
        fundamental_analysis = state.get('fundamental_analysis', '暂无基本面分析')
        technical_analysis = state.get('technical_analysis', '暂无技术面分析')
        real_time_data = state.get('real_time_data', {})
        stock_info = state.get('stock_info', {})
        alpha158 = state.get('alpha158', 0.0)
        
        prompt = f"""
请作为资深交易员，整合基本面和技术面分析结论，对 {stock_info.get('name')} ({state['stock_code']}) 进行最终研判。
你需要给出 T+1 交易指令以及未来一周（5个交易日）的行情走势预测。

数据：
- 基本面：{fundamental_analysis}
- 技术面：{technical_analysis}
- 价格：{real_time_data.get('current_price')} ({real_time_data.get('change_percent')}%)
- Alpha158: {alpha158:.4f}

要求：
1. 价格预测（目标价、入场价、止损价）必须基于技术面提供的支撑压力位给出精确数值，不得使用模糊区间。
2. 必须包含对未来一周（5个交易日）的具体走势预判及逻辑支撑。
3. 严格按以下JSON格式输出：
{{
  "stock_code": "{state['stock_code']}",
  "stock_name": "{stock_info.get('name')}",
  "current_price": {real_time_data.get('current_price', 0)},
  "analysis": "整合结论",
  "trend": "趋势",
  "weekly_outlook": "未来一周（5个交易日）走势预测及逻辑",
  "support": "支撑位数值",
  "resistance": "压力位数值",
  "recommendation": "买入/观望/卖出",
  "action": "具体交易指令",
  "predicted_price": 具体的预期目标价数值,
  "predicted_buy_price": 具体的建议买入价数值,
  "predicted_sell_price": 具体的建议止损价数值,
  "confidence": 0-1,
  "risk_warning": "风险点"
}}
"""
        messages = [
            SystemMessage(content="你是一位资深交易员。"),
            HumanMessage(content=prompt)
        ]
        
        print(f"[{state['stock_code']}] 交易员正在决策...")
        response = self.llm.invoke(messages)
        
        # 解析 JSON
        content = response.content.strip()
        try:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            result_dict = json.loads(content.strip())
        except Exception as e:
            print(f"解析交易员输出失败: {e}")
            result_dict = {
                "stock_code": state['stock_code'],
                "stock_name": stock_info.get('name'),
                "error": "解析失败",
                "raw_content": content,
                "analysis": "分析失败"
            }
            
        return {"final_result": result_dict}

    def _calculate_indicators(self, history_data):
        if not history_data or len(history_data) < 5:
            return {}
        # 历史数据是倒序的（最新在前面），为了计算均线需要先正序
        df = pd.DataFrame(history_data[::-1])
        df['ma5'] = df['close'].rolling(window=5).mean()
        df['ma10'] = df['close'].rolling(window=10).mean()
        df['ma20'] = df['close'].rolling(window=20).mean()
        df['ma60'] = df['close'].rolling(window=60).mean() if len(df) >= 60 else df['close'].rolling(window=len(df)).mean()
        df['vma5'] = df['volume'].rolling(window=5).mean()
        
        # 计算 MACD
        df['ema12'] = df['close'].ewm(span=12, adjust=False).mean()
        df['ema26'] = df['close'].ewm(span=26, adjust=False).mean()
        df['dif'] = df['ema12'] - df['ema26']
        df['dea'] = df['dif'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = (df['dif'] - df['dea']) * 2

        latest = df.iloc[-1]
        return {
            'ma5': round(float(latest['ma5']), 2) if not pd.isna(latest.get('ma5')) else 0,
            'ma10': round(float(latest['ma10']), 2) if not pd.isna(latest.get('ma10')) else 0,
            'ma20': round(float(latest['ma20']), 2) if not pd.isna(latest.get('ma20')) else 0,
            'ma60': round(float(latest['ma60']), 2) if not pd.isna(latest.get('ma60')) else 0,
            'macd_hist': round(float(latest['macd_hist']), 2) if not pd.isna(latest.get('macd_hist')) else 0,
            'vma5': round(float(latest['vma5']), 0) if not pd.isna(latest.get('vma5')) else 0,
            'volume_ratio': round(float(latest['volume'] / latest['vma5']), 2) if not pd.isna(latest.get('vma5')) and latest['vma5'] > 0 else 0,
            'current_price': round(float(latest['close']), 2)
        }

    def _is_promising(self, indicators, alpha158):
        """预筛选逻辑"""
        if not indicators: return False
        if alpha158 < -0.5: return False
        
        ma5 = indicators.get('ma5', 0)
        ma20 = indicators.get('ma20', 0)
        ma60 = indicators.get('ma60', 0)
        curr = indicators.get('current_price', 0)
        
        # 强空头排列且价格在下方
        if ma5 < ma20 < ma60 and curr < ma5:
            if indicators.get('macd_hist', 0) < 0:
                return False
        return True

    def build_graph(self):
        workflow = StateGraph(AgentState)
        
        workflow.add_node("fundamental_analyst", self.fundamental_analyst_node)
        workflow.add_node("technical_analyst", self.technical_analyst_node)
        workflow.add_node("trader", self.trader_node)
        
        # 并行运行基本面和技术面分析
        workflow.add_edge(START, "fundamental_analyst")
        workflow.add_edge(START, "technical_analyst")
        
        # 汇聚到交易员
        workflow.add_edge("fundamental_analyst", "trader")
        workflow.add_edge("technical_analyst", "trader")
        
        workflow.add_edge("trader", END)
        
        return workflow.compile()

    def run(self, stock_code: str):
        print(f"\n开始多角色流程分析，股票代码: {stock_code}")
        stock_info = self.db.get_stock_info(stock_code)
        if not stock_info:
            print(f"找不到股票代码 {stock_code}")
            return
            
        history_data = self.db.get_stock_history(stock_code, 30)
        real_time_data = self.db.get_real_time_data(stock_info.get('full_code'))
        indicators = self._calculate_indicators(history_data)
        
        alpha158 = 0.0
        if settings.enable_factor_analysis:
            alpha158_dict = self.db.get_factor_158([stock_code])
            alpha158 = alpha158_dict.get(stock_code, 0.0)
        
        # 预筛选
        if not self._is_promising(indicators, alpha158):
            print(f"[{stock_code}] 预筛选未通过，跳过流程。")
            result = {
                "stock_code": stock_code,
                "stock_name": stock_info.get('name', '未知'),
                "current_price": real_time_data.get('current_price', 0) if real_time_data else 0,
                "recommendation": "观望",
                "trend": "空头/下跌",
                "analysis": "预筛选拦截：技术指标显示强空头或因子分过低，目前无参与价值。",
                "action": "观望",
                "confidence": 0.1,
                "analysis_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "alpha158": alpha158
            }
            self._save(result)
            return result

        initial_state = {
            "stock_code": stock_code,
            "stock_info": stock_info,
            "history_data": history_data,
            "real_time_data": real_time_data,
            "indicators": indicators,
            "alpha158": alpha158,
            "fundamental_analysis": "",
            "technical_analysis": "",
            "final_result": {}
        }
        
        app = self.build_graph()
        final_state = app.invoke(initial_state)
        
        result = final_state.get('final_result', {})
        result['fundamental_analysis'] = final_state.get('fundamental_analysis', '')
        result['technical_analysis'] = final_state.get('technical_analysis', '')
        result['analysis_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        result['alpha158'] = alpha158
        
        # 保存结果
        self._save(result)
        return result

    def _save(self, result):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"flow_analysis_{result.get('stock_code')}_{timestamp}.xlsx"
        filepath = os.path.join(self.output_dir, filename)
        
        # 转换字典中的复杂类型
        save_data = {}
        for k, v in result.items():
            if isinstance(v, (dict, list)):
                save_data[k] = json.dumps(v, ensure_ascii=False)
            else:
                save_data[k] = v
                
        df = pd.DataFrame([save_data])
        
        # 映射中文表头
        column_mapping = {
            'stock_code': '股票代码',
            'stock_name': '股票名称',
            'analysis_time': '分析时间',
            'current_price': '当前价格',
            'alpha158': 'Alpha158因子',
            'fundamental_analysis': '基本面分析结论',
            'technical_analysis': '技术面分析结论',
            'analysis': '整合交易结论',
            'trend': '趋势',
            'weekly_outlook': '周度展望',
            'support': '支撑位',
            'resistance': '压力位',
            'recommendation': '投资建议',
            'action': '交易指令',
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
        
        df.to_excel(filepath, index=False)
        print(f"分析完成，结果已保存至: {filepath}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='股票多角色分析流程')
    parser.add_argument('--code', type=str, default='002283', help='股票代码')
    args = parser.parse_args()
    
    flow = AnalysisFlow()
    res = flow.run(args.code)
    if res:
        print("\n--- 分析结果摘要 ---")
        print(f"股票: {res.get('stock_name')} ({res.get('stock_code')})")
        
        print("\n[金牌股票基本面分析师结论]")
        print(res.get('fundamental_analysis'))
        
        print("\n[金牌资深股票数据分析师结论]")
        print(res.get('technical_analysis'))
        
        print("\n[金牌资深股票交易员整合建议]")
        print(res.get('analysis'))
        
        print("\n--- 交易执行指令 ---")
        print(f"建议: {res.get('recommendation')}")
        print(f"指令: {res.get('action')}")
        print(f"信心: {res.get('confidence')}")
        print("-------------------\n")
