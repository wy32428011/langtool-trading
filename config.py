from enum import Enum
from pydantic.v1 import BaseSettings


class LLMType(str, Enum):
    QWEN = "qwen"
    DEEPSEEK = "deepseek"
    SILICONFLOW = "siliconflow"


class Settings(BaseSettings):


    # db_host: str = "172.16.3.27"
    db_host: str = "192.168.60.140"
    # db_port: int = 49030
    db_port: int = 9030
    db_name: str = "stock"
    db_user: str = "root"
    db_password: str = ""
    db_polymarket: str = "polymarket"

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

    zdzn_base_url: str = "http://192.168.60.172:9090/v1"
    zdzn_model: str = "ZDZN"
    zdzn_api_key: str = "test_zdzn"

    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-reasoner"
    deepseek_api_key: str = ""

    vector_base_url: str = ""
    vector_model: str = ""
    vector_api_key: str = ""
    
    alchemy_api_key: str = "" # 在 .env 中设置 ALCHEMY_API_KEY
    
    poly_api_key: str = ""
    poly_api_secret: str = ""
    poly_api_passphrase: str = ""
    poly_private_key: str = ""

    enable_factor_analysis: bool = True
    class Config:
        env_file = ".env"

settings = Settings()