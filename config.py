from enum import Enum
from pydantic.v1 import BaseSettings


class LLMType(str, Enum):
    QWEN = "qwen"
    DEEPSEEK = "deepseek"
    SILICONFLOW = "siliconflow"


class Settings(BaseSettings):


    db_host: str = "172.16.3.27"
    db_port: int = 49030
    db_name: str = "stock"
    db_user: str = "root"
    db_password: str = ""

    llm_type: LLMType = LLMType.QWEN
    max_tokens: int = 2048
    llm_temperature: float = 0.1

    llm_base_url: str = "http://172.16.3.27:49090/v1"
    # llm_model: str = "Qwen3-235B-A22B-Instruct-2507"
    # llm_api_key: str = "test_qwen"
    llm_model: str = "DeepSeek-V3.2"
    llm_api_key: str = "test_deepseek"
    # llm_model: str = "GLM-4.7"
    # llm_api_key: str = "test_glm"

    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-reasoner"
    deepseek_api_key: str = ""


    enable_factor_analysis: bool = True
    class Config:
        env_file = ".env"

settings = Settings()