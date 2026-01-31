import os

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain_deepseek import ChatDeepSeek
from config import settings, LLMType


class Agent:
    def __init__(self):
        if settings.llm_type == LLMType.DEEPSEEK:
            self.model = ChatDeepSeek(
                base_url=settings.deepseek_base_url,
                model=settings.deepseek_model,
                api_key=settings.deepseek_api_key,
                max_tokens=settings.max_tokens,
                temperature=settings.llm_temperature,
            )
        else:
            # 默认使用 OpenAI 兼容接口 (如 Qwen, SiliconFlow 等)
            self.model = ChatOpenAI(
                base_url=settings.llm_base_url,
                model=settings.llm_model,
                api_key=settings.llm_api_key,
                max_tokens=settings.max_tokens,
                temperature=settings.llm_temperature,
            )
        
        self.system_prompt = (
            "你是一个拥有超过20年从业经验的资深股票数据分析师和金牌交易员。你擅长从海量的历史价格、成交量以及各种技术指标中洞察市场趋势。\n"
            "\n"
            "你的职责是：\n"
            "1. 接收并解析用户提供的股票历史数据（包括日期、开盘价、最高价、最低价、收盘价、成交量等）。\n"
            "2. 运用技术分析（如趋势线、形态学、均线系统及各类震荡指标）评估当前的趋势状态（上涨、下跌或震荡）。\n"
            "3. 识别关键的支撑位和阻力位。\n"
            "4. 基于数据推断未来短期和中长期的可能走势，并给出逻辑支撑。\n"
            "5. 提示潜在的风险点。\n"
            "\n"
            "请始终保持专业、理性、客观的态度。你的回复应结构清晰，逻辑严密，并明确标注你的分析仅供参考，不构成投资建议。"
        )


    def get_agent(self):

        return create_agent(model=self.model,
                            system_prompt=self.system_prompt)
