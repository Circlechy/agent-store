"""
类别配置管理

定义执行器类别及其配置（模型、温度、提示词等）
"""
from dataclasses import dataclass
from typing import Dict, Optional
from pathlib import Path
import yaml
from loguru import logger


@dataclass
class CategoryConfig:
    """类别配置"""
    name: str
    model_provider: str
    model_name: str
    temperature: float
    top_p: float
    timeout: int
    prompt_append: str  # 类别特定的提示词追加
    description: str


# 默认类别配置（3个核心类别）
DEFAULT_CATEGORIES: Dict[str, CategoryConfig] = {
    "general": CategoryConfig(
        name="general",
        model_provider="openai",
        model_name="qwen3-coder-plus",
        temperature=0.3,
        top_p=0.9,
        timeout=120,
        prompt_append="通用任务执行。专注于代码实现、文件操作、工具调用。",
        description="通用任务，适合所有场景"
    ),
    "coder": CategoryConfig(
        name="coder",
        model_provider="openai",
        model_name="qwen3-coder-plus",
        temperature=0.2,
        top_p=0.9,
        timeout=120,
        prompt_append="代码生成任务。专注于生成高质量、可运行的代码。注意代码规范、错误处理和最佳实践。",
        description="代码生成任务，适合代码编写场景"
    ),
    "docgen": CategoryConfig(
        name="docgen",
        model_provider="openai",
        model_name="qwen-turbo",
        temperature=0.3,
        top_p=0.9,
        timeout=120,
        prompt_append="文档生成任务。专注于文档编写、README生成、代码注释、API文档。使用清晰、结构化的文档风格。",
        description="文档生成任务，适合文档编写场景"
    )
}


def load_category_from_yaml(category: str, config_path: Optional[Path] = None) -> Optional[CategoryConfig]:
    """
    从 YAML 配置文件加载类别配置
    
    Args:
        category: 类别名称
        config_path: 配置文件路径（可选）
    
    Returns:
        类别配置，如果不存在则返回 None
    """
    if config_path is None:
        # 默认查找项目根目录的 categories.yaml
        config_path = Path(__file__).parent.parent.parent / "categories.yaml"
    
    if not config_path.exists():
        return None
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f)
        
        if not config_data or "categories" not in config_data:
            return None
        
        categories = config_data["categories"]
        if category not in categories:
            return None
        
        cat_data = categories[category]
        return CategoryConfig(
            name=category,
            model_provider=cat_data.get("model_provider", "openai"),
            model_name=cat_data.get("model_name", "qwen3-coder-plus"),
            temperature=float(cat_data.get("temperature", 0.3)),
            top_p=float(cat_data.get("top_p", 0.9)),
            timeout=int(cat_data.get("timeout", 120)),
            prompt_append=cat_data.get("prompt_append", ""),
            description=cat_data.get("description", "")
        )
    except Exception as e:
        logger.warning(f"加载类别配置失败: {category}, 错误: {e}")
        return None


def get_category_config(category: str) -> CategoryConfig:
    """
    获取类别配置
    
    优先级：
    1. 默认配置（DEFAULT_CATEGORIES）
    2. YAML 配置文件
    3. 默认返回 general 类别
    
    Args:
        category: 类别名称
    
    Returns:
        类别配置
    """
    # 1. 尝试从默认配置获取
    if category in DEFAULT_CATEGORIES:
        return DEFAULT_CATEGORIES[category]
    
    # 2. 尝试从配置文件加载
    config = load_category_from_yaml(category)
    if config:
        return config
    
    # 3. 默认返回 general
    logger.warning(f"类别 {category} 不存在，使用默认 general 类别")
    return DEFAULT_CATEGORIES["general"]


def get_all_categories() -> Dict[str, CategoryConfig]:
    """获取所有类别配置"""
    result = DEFAULT_CATEGORIES.copy()
    
    # 尝试从配置文件加载额外类别
    config_path = Path(__file__).parent.parent.parent / "categories.yaml"
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f)
            
            if config_data and "categories" in config_data:
                for cat_name, cat_data in config_data["categories"].items():
                    if cat_name not in result:
                        result[cat_name] = CategoryConfig(
                            name=cat_name,
                            model_provider=cat_data.get("model_provider", "openai"),
                            model_name=cat_data.get("model_name", "qwen3-coder-plus"),
                            temperature=float(cat_data.get("temperature", 0.3)),
                            top_p=float(cat_data.get("top_p", 0.9)),
                            timeout=int(cat_data.get("timeout", 120)),
                            prompt_append=cat_data.get("prompt_append", ""),
                            description=cat_data.get("description", "")
                        )
        except Exception as e:
            logger.warning(f"加载额外类别配置失败: {e}")
    
    return result
