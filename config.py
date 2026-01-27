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

    llm_base_url: str = "http://172.16.3.27:49090/v1"
    llm_model: str = "Qwen3-235B-A22B-Instruct-2507"
    llm_api_key: str = "test_qwen"

    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-reasoner"
    deepseek_api_key: str = "sk-d530181b3b484b4084cf099a1b4da31b"
    class Config:
        env_file = ".env"

settings = Settings()