from enum import Enum
from pydantic.v1 import BaseSettings


class LLMType(str, Enum):
    QWEN = "qwen"
    DEEPSEEK = "deepseek"
    SILICONFLOW = "siliconflow"


class Settings(BaseSettings):


    db_host: str = "192.168.60.140"
    db_port: int = 9030
    db_name: str = "stock"
    db_user: str = "root"
    db_password: str = ""

    llm_type: LLMType = LLMType.QWEN

    llm_base_url: str = "http://192.168.60.172:9090/v1"
    llm_model: str = "GLM-4.7"
    llm_api_key: str = "test_glm"

    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-reasoner"
    deepseek_api_key: str = ""


    enable_factor_analysis: bool = True
    class Config:
        env_file = ".env"

settings = Settings()