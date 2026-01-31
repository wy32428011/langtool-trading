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
        你是一位金牌股票基本面分析师。请根据以下信息对股票 {stock_info.get('name')} ({state['stock_code']}) 进行基本面分析。
        
        ### 股票信息
        - 行业: {stock_info.get('sector', '未知')}
        - 业务描述: {stock_info.get('description', '暂无')}
        
        ### 实时财务数据
        - 市盈率(PE): {real_time_data.get('pe_ratio', 'N/A')}
        - 市净率(PB): {real_time_data.get('pb_ratio', 'N/A')}
        
        请分析该公司的行业地位、估值水平以及潜在的基本面风险或机会。
        你的分析应专业、客观。
        """
        
        messages = [
            SystemMessage(content="你是一位拥有20年从业经验的金牌股票基本面分析师，擅长从宏观经济、行业趋势和公司财务状况中挖掘投资价值。"),
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
        
        history_list = []
        # 展示最近30天
        for d in history_data[:30]:
            turn_str = f"{d.get('turn', 0)}%" if d.get('turn') else "N/A"
            history_list.append(
                f"{d['date']}: 开盘={d['open']}, 最高={d['high']}, 最低={d['low']}, 收盘={round(d['close'], 2)}, "
                f"涨跌幅={d['pctChg']}%, 成交量={d['volume']}, 换手率={turn_str}"
            )
        history_summary = "\n".join(history_list)
        
        prompt = f"""
        你是一位金牌资深股票数据分析师。请根据以下历史数据和技术指标对股票 {state['stock_code']} 进行量价分析和技术面研判。
        
        ### 技术指标
        - 均线系统: MA5={indicators.get('ma5', 'N/A')}, MA10={indicators.get('ma10', 'N/A')}, MA20={indicators.get('ma20', 'N/A')}
        - 成交量均线: VMA5={indicators.get('vma5', 'N/A')}, VMA10={indicators.get('vma10', 'N/A')}
        - 量比: {indicators.get('volume_ratio', 'N/A')}
        - 智能预测因子 (Alpha158): {alpha158:.4f} (基于量价多因子模型，正值越大代表短期看涨信号越强)
        
        ### 最近30个交易日历史走势
        {history_summary}
        
        请分析当前价格趋势（上涨/下跌/震荡）、量价关系是否健康、支撑压力位以及Alpha158因子传达的信号。
        """
        
        messages = [
            SystemMessage(content="你是一位金牌资深股票数据分析师，精通各类量化指标和技术分析手段，擅长通过数据洞察市场情绪和趋势。"),
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
        你是一位金牌资深股票交易员。请结合以下基本面分析和技术面分析，对股票 {stock_info.get('name')} ({state['stock_code']}) 做出最终的交易判断。
        
        ### 1. 基本面分析结论
        {fundamental_analysis}
        
        ### 2. 技术面分析结论
        {technical_analysis}
        
        ### 3. 实时行情
        - 当前价格: {real_time_data.get('current_price', 0)}
        - 今日涨跌幅: {real_time_data.get('change_percent', 0)}%
"""
        if settings.enable_factor_analysis:
            prompt += f"        - 智能预测因子 (Alpha158): {alpha158:.4f}\n"

        prompt += f"""
        ### 任务
        请综合多方因素，给出最终的交易建议和价格预测。**交易指令(action)应当包含股票名称和代码，且描述应具体详尽，包含具体的操作动作、仓位建议或关键触发条件。**
"""
        if settings.enable_factor_analysis:
            prompt = prompt.replace("综合多方因素", "综合多方因素（包括Alpha158因子结论）")

        prompt += f"""
        请严格按以下JSON格式返回，不要有任何多余的文字说明：
        {{
          "stock_code": "{state['stock_code']}",
          "stock_name": "{stock_info.get('name')}",
          "current_price": {real_time_data.get('current_price', 0)},
          "analysis": "最终整合分析结论",
          "trend": "上涨/下跌/震荡",
          "support": "支撑位价格",
          "resistance": "压力位价格",
          "recommendation": "买入/卖出/观望",
          "action": "详细的交易指令（需包含股票名称和代码，并提供具体的操作逻辑）",
          "predicted_price": "预期目标价",
          "predicted_buy_price": "建议买入价",
          "predicted_sell_price": "建议止盈/止损价",
          "confidence": 0.85,
          "risk_warning": "核心风险提示"
        }}
        """
        
        messages = [
            SystemMessage(content="你是一位拥有20年实战经验的金牌资深股票交易员，擅长权衡风险与收益。你负责整合分析师的意见并给出最终可执行的建议。"),
            HumanMessage(content=prompt)
        ]
        
        print(f"[{state['stock_code']}] 交易员正在做决策...")
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
        df['vma5'] = df['volume'].rolling(window=5).mean()
        latest = df.iloc[-1]
        return {
            'ma5': round(float(latest['ma5']), 2) if not pd.isna(latest.get('ma5')) else 0,
            'ma10': round(float(latest['ma10']), 2) if not pd.isna(latest.get('ma10')) else 0,
            'ma20': round(float(latest['ma20']), 2) if not pd.isna(latest.get('ma20')) else 0,
            'vma5': round(float(latest['vma5']), 0) if not pd.isna(latest.get('vma5')) else 0,
            'volume_ratio': round(float(latest['volume'] / latest['vma5']), 2) if not pd.isna(latest.get('vma5')) and latest['vma5'] > 0 else 0
        }

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
