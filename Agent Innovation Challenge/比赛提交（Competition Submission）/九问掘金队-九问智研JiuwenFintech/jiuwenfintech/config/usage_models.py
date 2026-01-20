from dataclasses import dataclass
from typing import Optional


@dataclass
class UsageRecord:
    """使用记录"""
    timestamp: str
    provider: str
    model_name: str
    input_tokens: int
    output_tokens: int
    cost: float
    currency: str = "CNY"
    session_id: str = ""
    analysis_type: str = "stock_analysis"


@dataclass
class ModelConfig:
    """模型配置"""
    provider: str
    model_name: str
    api_key: str
    base_url: Optional[str] = None
    max_tokens: int = 4000
    temperature: float = 0.7
    enabled: bool = True


@dataclass
class PricingConfig:
    """定价配置"""
    provider: str
    model_name: str
    input_price_per_1k: float
    output_price_per_1k: float
    currency: str = "CNY"

