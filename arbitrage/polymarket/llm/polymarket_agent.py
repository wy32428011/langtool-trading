import json
from langchain_openai import ChatOpenAI
from config import settings
from typing import List, Tuple, Any, Dict

class PolyMarketAgent:
    """
    Polymarket 智能代理
    
    使用大语言模型 (LLM) 分析预测市场的问题、结果及其逻辑组合。
    支持多种模型后端，如 ZDZN, DeepSeek 和 Qwen。
    """
    def __init__(self, model: ChatOpenAI = None, model_type: str = "zdzn"):
        """
        初始化 Polymarket Agent
        
        Args:
            model: 可选的 ChatOpenAI 实例。如果提供，将直接使用。
            model_type: 模型类型，可选 "zdzn", "deepseek" 或其他 (默认使用 Qwen 相关的配置)。
        """
        if model:
            self.model = model
        else:
            if model_type == "zdzn":
                self.model = ChatOpenAI(
                    base_url=settings.zdzn_base_url,
                    model=settings.zdzn_model,
                    api_key=settings.zdzn_api_key,
                    temperature=settings.llm_temperature,
                    max_retries=3,
                )
            elif model_type == "deepseek":
                self.model = ChatOpenAI(
                    base_url=settings.deepseek_base_url,
                    model=settings.deepseek_model,
                    api_key=settings.deepseek_api_key,
                    temperature=settings.llm_temperature,
                    max_retries=3,
                )
            else:
                # 默认使用 settings.llm_ (如 Qwen)
                self.model = ChatOpenAI(
                    base_url=settings.vector_base_url,
                    model=settings.vector_model,
                    api_key=settings.vector_api_key,
                    temperature=settings.llm_temperature,
                    max_retries=3,
                )

    def get_prompt(self, statements):
        """
        根据提供的声明列表生成用于分析逻辑组合的提示词
        
        Args:
            statements: 包含 (id, statement) 元组的列表。
            
        Returns:
            str: 生成好的提示词字符串。
        """
        prompt = f"You are given a set of binary (True/False) questions. Your task is to determine all valid logical combinations of truth values these questions can take. Rules: 1. Each tuple represents a possible valid assignment of truth values. 2. Each tuple must contain exactly {len(statements)} values, corresponding to the listed questions. 3. The output must be a JSON array where each entry is a list of Boolean values. 4. The output must be valid JSON and contain no additional text."
        prompt += f"Questions:"
        
        for idx, (_, statement) in enumerate(statements):
            prompt += f"- ({idx}) {statement}"
        
        prompt += "Expected Output Format: {'valid_combinations': [ [true,false,...], [false,true,...],[...] ]}  Ensure the output is strictly formatted as JSON without any additional explanation or formatting artifacts."
        return prompt

    def analyze_combinations(self, statements: List[Tuple[Any, str]]):
        """
        分析声明的有效逻辑组合
        
        Args:
            statements: 包含 (id, statement) 元组的列表。
            
        Returns:
            Dict: 包含 'valid_combinations' 键或 'error' 键的字典。
        """
        prompt = self.get_prompt(statements)
        try:
            response = self.model.invoke(prompt)
            content = response.content
        except Exception as e:
            return {"error": f"LLM invocation failed: {str(e)}", "raw_content": None}
        
        # 尝试解析 JSON
        try:
            # 提取 JSON 部分（防止模型返回包含 ```json 的 Markdown）
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].strip()
            
            return json.loads(content)
        except Exception as e:
            return {"error": f"Failed to parse JSON: {str(e)}", "raw_content": response.content}

    def generate_questions(self, question: str, outcomes: List[str], description: str = None) -> List[str]:
        """
        根据原始问题、结果选项以及详细描述生成对应的疑问句列表
        
        Args:
            question: 市场的主问题。
            outcomes: 可能的结果列表。
            description: 可选的市场背景描述。
            
        Returns:
            List[str]: 为每个结果生成的特定问题列表。
        """
        prompt = f"Original question: {question}\nOutcomes: {outcomes}\n"
        if description:
            prompt += f"Description: {description}\n"
        prompt += "Please generate one natural, concise question for each outcome that asks whether that specific outcome will happen. "
        prompt += "Use the provided Description to better understand the rules and context of the question. "
        prompt += "The output must be a JSON array of strings, where each string is a question corresponding to the outcome at the same index in the 'outcomes' list. "
        prompt += "Just return the JSON array, no extra text."
        
        try:
            response = self.model.invoke(prompt)
            content = response.content.strip()
            # 提取 JSON 部分
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].strip()
            
            return json.loads(content)
        except Exception as e:
            # 降级处理：如果解析失败，尝试为每个 outcome 生成一个简单的问题
            try:
                # 再次尝试简单的 prompt
                results = []
                for outcome in outcomes:
                    if outcome.lower() in ["yes", "no"]:
                        results.append(question)
                    else:
                        results.append(f"Will the outcome '{outcome}' happen for the question: {question}?")
                return results
            except:
                return [f"Error: {str(e)}"]

    def analyze_market(self, market_data: Any):
        """
        高层级接口：传入市场数据对象或字典，自动提取问题并分析其逻辑组合
        
        Args:
            market_data: 市场数据，可以是对象、字典或它们的列表。
            
        Returns:
            Dict: 分析结果字典。
        """
        # 如果是 Market 模型对象，提取其 question
        if hasattr(market_data, 'question'):
            statements = [(0, market_data.question)]
        elif isinstance(market_data, dict) and 'question' in market_data:
            statements = [(0, market_data['question'])]
        elif isinstance(market_data, list):
            # 假设是多个 market
            statements = []
            for idx, m in enumerate(market_data):
                if hasattr(m, 'question'):
                    statements.append((idx, m.question))
                elif isinstance(m, dict) and 'question' in m:
                    statements.append((idx, m['question']))
                else:
                    statements.append((idx, str(m)))
        else:
            statements = [(0, str(market_data))]
            
        return self.analyze_combinations(statements)
